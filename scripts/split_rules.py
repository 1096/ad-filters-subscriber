#!/usr/bin/env python3
"""Split generated rule files into independently usable, size-limited parts."""

import json
import os
from pathlib import Path
import sys
import tempfile

MAX_BYTES = 7_000_000
MANIFEST = "split-manifest.json"


def part_name(name, number):
    path = Path(name)
    return name if number == 1 else f"{path.stem}-{number}{path.suffix}"


def read_manifest(directory):
    path = directory / MANIFEST
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or data.get("version") != 1 or not isinstance(data.get("files"), dict):
        raise ValueError(f"Invalid split manifest: {path}")
    files = data["files"]
    for name, parts in files.items():
        if (not isinstance(name, str) or Path(name).name != name
                or not isinstance(parts, list) or not parts
                or parts != [part_name(name, i) for i in range(1, len(parts) + 1)]):
            raise ValueError(f"Invalid split manifest entry: {name}")
    return files


def split_file(source, destination, max_bytes):
    parts = []
    with source.open("rb") as reader:
        header = bytearray()
        line = reader.readline()
        while line and (line.startswith((b"#", b"!", b"[")) or not line.strip()):
            header.extend(line)
            line = reader.readline()
        if source.suffix == ".yaml":
            if line.strip() != b"payload:":
                raise ValueError(f"Missing Clash payload header in {source}")
            header.extend(line)
            line = reader.readline()
        if len(header) > max_bytes:
            raise ValueError(f"Header exceeds size limit: {source}")

        writer = None
        try:
            def open_part():
                name = part_name(source.name, len(parts) + 1)
                parts.append(name)
                stream = (destination / name).open("wb")
                stream.write(header)
                return stream, len(header)

            writer, size = open_part()
            while line:
                if len(header) + len(line) > max_bytes:
                    raise ValueError(f"Rule exceeds size limit in {source}")
                if size + len(line) > max_bytes:
                    writer.close()
                    writer, size = open_part()
                writer.write(line)
                size += len(line)
                line = reader.readline()
        finally:
            if writer is not None:
                writer.close()
    return parts


def split_directory(directory, max_bytes=MAX_BYTES):
    directory = Path(directory)
    if max_bytes <= 0 or not directory.is_dir():
        raise ValueError(f"Invalid output directory or size limit: {directory}")
    old = read_manifest(directory)
    old_parts = {part for parts in old.values() for part in parts[1:]}
    sources = sorted(
        p for p in directory.iterdir()
        if p.is_file() and p.suffix in {".txt", ".yaml"} and p.name not in old_parts
    )
    if not sources:
        raise ValueError(f"No generated rule files in {directory}")

    with tempfile.TemporaryDirectory(prefix="split-rules-", dir=directory.parent) as temporary:
        staging = Path(temporary)
        files = {}
        claimed = set()
        source_names = {p.name for p in sources}
        for source in sources:
            parts = split_file(source, staging, max_bytes)
            for name in parts:
                if name in claimed or (name != source.name and (
                        name in source_names or ((directory / name).exists() and name not in old_parts))):
                    raise ValueError(f"Output filename collision: {name}")
                claimed.add(name)
            files[source.name] = parts
        manifest = {"version": 1, "max_bytes": max_bytes, "files": files}
        (staging / MANIFEST).write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        for name in sorted(claimed):
            os.replace(staging / name, directory / name)
        os.replace(staging / MANIFEST, directory / MANIFEST)
        for name in sorted(old_parts - claimed):
            (directory / name).unlink(missing_ok=True)
    for name, parts in files.items():
        print(f"{name}: {len(parts)} part(s)")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("Usage: python scripts/split_rules.py OUTPUT_DIRECTORY")
    try:
        split_directory(sys.argv[1])
    except (OSError, ValueError) as error:
        raise SystemExit(f"Rule splitting failed: {error}") from error
