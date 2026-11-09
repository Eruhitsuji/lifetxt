"""Regression coverage for the standalone Graph relationship list."""

import json
import shutil
import subprocess
import unittest

from tests.test_web_drawer_edit_js import _extract_function
from tests.test_web_native_timeline_visual import _extract_script


@unittest.skipUnless(shutil.which("node"), "Node.js unavailable")
class GraphRelationsTests(unittest.TestCase):
    def test_graph_load_renders_bounded_localized_list_and_preserves_svg(self):
        source = _extract_script()
        signatures = [
            "function escapeHtml(",
            "function jsLiteral(",
            "function drawerText(",
            "function drawerRelationLabel(",
            "function graphRelationEndpoint(",
            "function renderGraphRelations(",
            "async function loadGraphPanel(",
        ]
        functions = "\n".join(_extract_function(source, sig) for sig in signatures)
        run = subprocess.run(
            [
                "node",
                "-e",
                functions
                + r"""
let lang = "ja", graphLoaded;
const currentLanguage = () => lang;
const title = '<長い名前 & "title">';
const id = "source');alert(1)//";
const nodes = [
  {id, title}, {id:"target", title:"Target title"},
  {id:"missing", missing:true}, {id:"/input/life.txt:42", title:"No ID"},
];
const edge = {source:id, target:"target", relation:"depends_on"};
const edges = [edge, {source:"/input/life.txt:42", target:"missing", relation:"<custom>"}];
const panel = {innerHTML:"", querySelector:() => ({open:true})};
const inputs = {"graph-panel":panel, "graph-root":{value:"root"}, "graph-depth":{value:"2"}};
const document = {getElementById:id => inputs[id]};
let requested;
const api = async url => { requested = url; return {nodes, edges}; };
const _graphLayout = "force";
const renderGraphSvg = (n, e, options) =>
  n === nodes && e === edges && options.layout === "force" && options.focusId === "root"
    ? "<svg></svg>" : "unexpected SVG input";
(async () => {
  await loadGraphPanel();
  const ja = panel.innerHTML;
  lang = "en";
  const en = renderGraphRelations(nodes, edges);
  const limited = renderGraphRelations(nodes, Array(101).fill(edge));
  console.log(JSON.stringify({ja, en, limited, requested, empty:renderGraphRelations(nodes, [])}));
})();
""",
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        result = json.loads(run.stdout)
        self.assertEqual("/api/graph?root=root&depth=2", result["requested"])
        ja = result["ja"]
        en = result["en"]
        self.assertIn("<summary>関係を一覧で表示</summary>", ja)
        self.assertIn("data-no-i18n open>", ja)
        self.assertIn("<svg></svg>", ja)
        self.assertIn("待っている項目", ja)
        self.assertIn("<summary>Show relationships as a list</summary>", en)
        self.assertIn("&lt;長い名前 &amp; &quot;title&quot;&gt;", en)
        self.assertIn(
            'onclick="drawerNavigate(&quot;source&#39;);alert(1)//&quot;)">', en
        )
        self.assertLess(en.index("長い名前"), en.index("Waiting on"))
        self.assertLess(en.index("Waiting on"), en.index("Target title"))
        self.assertIn("&lt;custom&gt;", en)
        self.assertIn("Missing record", en)
        self.assertIn("No linkable ID", en)
        self.assertNotIn("/input/life.txt:42", en)
        self.assertEqual(2, en.count('<button type="button"'))
        self.assertEqual(100, result["limited"].count("<li>"))
        self.assertIn("first 100 of 101", result["limited"])
        self.assertIn("No relationships in these results.", result["empty"])
