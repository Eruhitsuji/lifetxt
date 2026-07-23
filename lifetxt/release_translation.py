"""Translation-policy helpers shared by release checks.

The Web dictionary is a JavaScript object rather than JSON.  Keys may appear on
the same line as the opening brace in tests or generated pages, so extraction
must not depend on one-key-per-line formatting.
"""

from __future__ import unicode_literals

import re


def dictionary_keys(html):
    from . import release_policy

    whole = release_policy._extract_braced(html, "const UI_STRINGS")
    japanese = release_policy._extract_braced(whole, "ja:")
    pattern = re.compile(r'(?:^|[\{,])\s*"((?:\\.|[^"\\])*)"\s*:', re.M)
    return set(
        match.group(1).replace('\\"', '"').replace("\\\\", "\\")
        for match in pattern.finditer(japanese)
    )


def install_release_translation_parser():
    from . import release_policy

    release_policy._dictionary_keys = dictionary_keys
