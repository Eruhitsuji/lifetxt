"""Today discloses the remainder of the same ordered record set (#1459)."""

import json
import shutil
import subprocess
import unittest
from html.parser import HTMLParser
from lifetxt.web_assets import HTML_PAGE


class Rows(HTMLParser):
    def __init__(self, html):
        super().__init__()
        self.inside = False
        self.first = []
        self.remaining = []
        self.summaries = 0
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "details":
            self.inside = True
            assert "open" not in attrs
        if tag == "summary":
            self.summaries += 1
        if "data-row" in attrs:
            (self.remaining if self.inside else self.first).append(attrs["data-row"])

    def handle_endtag(self, tag):
        if tag == "details":
            self.inside = False


@unittest.skipUnless(shutil.which("node"), "Node.js unavailable")
class TodayMoreTests(unittest.TestCase):
    def test_same_ordered_rows_are_split_without_loss_or_duplicates(self):
        start = HTML_PAGE.index("    function _todaySubsection(")
        end = HTML_PAGE.index("    // Omitted entirely", start)
        harness = r"""
const TODAY_ROW_LIMIT=8;
function escapeHtml(s){return String(s).replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;').replaceAll('"','&quot;');}
let lang='en';function t(s){return lang==='ja'?'残りのレコードを表示':s;}
function _todayRefRow(r){return `<div data-row="${r.line}">${escapeHtml(r.title)}</div>`;}
const out=[];
for(lang of ['en','ja'])for(const n of [0,1,8,9,12])out.push({lang,n,html:_todaySubsection('<unsafe>',Array.from({length:n},(_,i)=>({line:i+1,title:'<row>'})), 'Empty')});
console.log(JSON.stringify(out));
"""
        result = subprocess.run(
            ["node", "-e", HTML_PAGE[start:end] + harness],
            capture_output=True,
            text=True,
            timeout=10,
        )
        self.assertEqual(0, result.returncode, result.stderr)
        for case in json.loads(result.stdout):
            with self.subTest(case["lang"], n=case["n"]):
                rows = Rows(case["html"])
                n = case["n"]
                self.assertEqual([str(i + 1) for i in range(min(8, n))], rows.first)
                self.assertEqual([str(i + 1) for i in range(8, n)], rows.remaining)
                self.assertEqual(int(n > 8), rows.summaries)
                self.assertNotIn("<unsafe>", case["html"])
                self.assertNotIn("<row>", case["html"])
                if n > 8:
                    self.assertIn(
                        "Show remaining records"
                        if case["lang"] == "en"
                        else "残りのレコードを表示",
                        case["html"],
                    )
                if n == 0:
                    self.assertIn("Empty", case["html"])
