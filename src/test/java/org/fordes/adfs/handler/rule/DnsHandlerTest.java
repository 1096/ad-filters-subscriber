package org.fordes.adfs.handler.rule;

import org.junit.jupiter.api.Test;

import java.util.regex.Pattern;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

class DnsHandlerTest {

    private final DnsHandler handler = new DnsHandler();

    @Test
    void convertsWildcardToValidRegexWithoutUrlRuleDecorations() {
        String output = handler.format(handler.parse("||*.exaapi.com^"));
        assertEquals("/(^|\\.).*\\.exaapi\\.com$/", output);
        Pattern pattern = Pattern.compile(output.substring(1, output.length() - 1));
        assertTrue(pattern.matcher("foo.exaapi.com").find());
        assertFalse(pattern.matcher("fooXexaapi.com").find());
        assertFalse(pattern.matcher("foo.exaapi.com.example").find());
    }

    @Test
    void convertsLeadingWildcardAndEscapesLiteralDots() {
        String output = handler.format(handler.parse("*.91ivr."));
        assertEquals("/.*\\.91ivr\\./", output);
        Pattern pattern = Pattern.compile(output.substring(1, output.length() - 1));
        assertTrue(pattern.matcher("ad.91ivr.example").find());
        assertFalse(pattern.matcher("adX91ivrXexample").find());
    }

    @Test
    void retainsExceptionsAndImportantModifiers() {
        assertEquals("@@/(^|\\.)ad.*\\.example\\.com$/$important",
                handler.format(handler.parse("@@||ad*.example.com^$important")));
    }

    @Test
    void preservesOrdinaryDomainRules() {
        assertEquals("||example.com^", handler.format(handler.parse("||example.com^")));
    }
}
