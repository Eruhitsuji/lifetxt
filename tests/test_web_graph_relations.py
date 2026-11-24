"""Regression coverage for the standalone Graph relationship list."""

import json
import shutil
import subprocess
import unittest

from tests.test_web_drawer_edit_js import _extract_function
from tests.test_web_i18n import _ja_dictionary
from tests.test_web_native_timeline_visual import _extract_script


@unittest.skipUnless(shutil.which("node"), "Node.js unavailable")
class GraphRelationsTests(unittest.TestCase):
    def test_force_labels_prioritize_root_and_keep_every_node_and_title(self):
        source = _extract_script()
        functions = "\n".join(
            _extract_function(source, f"function {name}(")
            for name in (
                "escapeHtml",
                "jsLiteral",
                "truncateLabel",
                "graphColor",
                "placeForceNodeLabels",
                "renderGraphSvg",
            )
        )
        run = subprocess.run(
            ["node"],
            input=functions
            + r"""
const assert = require("node:assert/strict");
const positions = {
  root: {x: 300, y: 140},
  neighbor: {x: 383, y: 134},
  clipped: {x: 45, y: 150},
  obstructed: {x: 480, y: 180},
  obstacle: {x: 500, y: 210},
};
const nodes = [
  {id: "neighbor", title: "隣接ノードの長い表示タイトルの続き"},
  {id: "root", title: "起点ノードの長い表示タイトルの続き"},
  {id: "clipped", title: '左端の長いタイトル <full & text>'},
  {id: "obstructed", title: "Behind node"},
  {id: "obstacle", title: "Other"},
];
const computeForcePositions = () => positions;
const computeLayeredPositions = () => positions;
const edges = [{source: "root", target: "clipped", relation: "related"}];
const nodeGroup = (svg, id) => [...svg.matchAll(/<g class="graph-node[^]*?<\/g>/g)]
  .map(match => match[0]).find(group => group.includes(`<title>${id} `));
const labelY = (svg, id) => nodeGroup(svg, id).match(/<text[^>]* y="(-?\d+)"/)?.[1];
const force = renderGraphSvg(nodes, edges, {layout: "force", focusId: "root"});
assert.equal(labelY(force, "root"), "37");
assert.equal(labelY(force, "neighbor"), "-26");
assert.equal(labelY(force, "clipped"), undefined);
assert.equal(labelY(force, "obstructed"), "-26");
assert.match(nodeGroup(force, "clipped"), /&lt;full &amp; text&gt;<\/title>/);
assert.match(nodeGroup(force, "clipped"), /onclick="drawerNavigate/);
assert.equal(force.match(/<circle /g).length, nodes.length);
assert.equal(force.match(/<line /g).length, edges.length);
for (const layout of ["ring", "lr", "tb", "force"]) {
  const compact = layout === "force";
  const svg = renderGraphSvg(nodes, edges, {layout, compact});
  assert.equal(labelY(svg, "neighbor"), compact ? "27" : "33");
  assert.equal(labelY(svg, "clipped"), compact ? "27" : "33");
}
""",
            capture_output=True,
            text=True,
            timeout=10,
        )
        self.assertEqual(run.returncode, 0, run.stderr)

    def test_graph_load_keeps_latest_results_and_renders_bounded_localized_list(self):
        source = _extract_script()
        signatures = [
            "function escapeHtml(",
            "function jsLiteral(",
            "function drawerText(",
            "function drawerRelationLabel(",
        ]
        functions = "\n".join(_extract_function(source, sig) for sig in signatures)
        graph_start = source.index("    function graphRelationEndpoint(")
        graph_end = source.index(
            "    // ── Native Timeline visual explorer", graph_start
        )
        functions += "\n" + source[graph_start:graph_end]
        run = subprocess.run(
            [
                "node",
                "-e",
                functions
                + r"""
let lang = "ja", graphLoaded;
const assert = require("node:assert/strict");
const dictionary = JSON.parse(require("node:fs").readFileSync(0, "utf8"));
const t = text => lang === "ja" ? dictionary[text] || text : text;
const currentLanguage = () => lang;
const title = '<長い名前 & "title">';
const id = "source');alert(1)//";
const nodes = [
  {id, title}, {id:"target", title:"Target title"},
  {id:"missing", missing:true}, {id:"/input/life.txt:42", title:"No ID"},
];
const edge = {source:id, target:"target", relation:"depends_on"};
const edges = [edge, {source:"/input/life.txt:42", target:"missing", relation:"<custom>"}];
const panel = {
  innerHTML:'<details class="graph-relations" data-no-i18n open></details>',
  querySelector:() => panel.innerHTML.includes('class="graph-relations"')
    ? {open: panel.innerHTML.includes("data-no-i18n open>")}
    : null,
};
const inputs = {"graph-panel":panel, "graph-root":{value:"root"}, "graph-depth":{value:"2"}};
const document = {getElementById:id => inputs[id]};
const requests = [];
const api = url => new Promise((resolve, reject) => requests.push({url, resolve, reject}));
const _graphLayout = "force";
const renderGraphSvg = (n, e, options) =>
  n === nodes && e === edges && options.layout === "force" && options.focusId === "root"
    ? "<svg></svg>" : "unexpected SVG input";
(async () => {
  const first = loadGraphPanel();
  assert.match(panel.innerHTML, /role="status">関係グラフを読み込み中…/);
  requests[0].resolve({nodes, edges});
  await first;
  const ja = panel.innerHTML;

  inputs["graph-root"].value = "older";
  const older = loadGraphPanel();
  inputs["graph-root"].value = "root";
  const latest = loadGraphPanel();
  requests[2].resolve({nodes, edges});
  await latest;
  assert.equal(panel.innerHTML, ja);
  requests[1].resolve({nodes: [], edges: []});
  await older;
  assert.equal(panel.innerHTML, ja, "stale empty result must not replace the graph");

  panel.innerHTML = ja.replace("data-no-i18n open>", "data-no-i18n>");
  const staleFailure = loadGraphPanel();
  const fresh = loadGraphPanel();
  requests[4].resolve({nodes, edges});
  await fresh;
  const closed = panel.innerHTML;
  assert.match(closed, /data-no-i18n>/);
  requests[3].reject(new Error("stale failure"));
  await staleFailure;
  assert.equal(panel.innerHTML, closed);

  panel.innerHTML = ja;
  const staleSuccess = loadGraphPanel();
  const freshFailure = loadGraphPanel();
  requests[6].reject(new Error("latest failure"));
  await freshFailure;
  const error = panel.innerHTML;
  assert.match(error, /role="status">関係グラフを読み込めませんでした。/);
  assert.match(error, /グラフを再読み込み/);
  assert.doesNotMatch(error, /latest failure/);
  requests[5].resolve({nodes, edges});
  await staleSuccess;
  assert.equal(panel.innerHTML, error);

  inputs["graph-depth"].value = "3";
  const retryAction = error.match(/onclick="([^"]+)"/)[1];
  const retry = eval(retryAction);
  assert.equal(requests[7].url, "/api/graph?root=root&depth=3");
  requests[7].resolve({nodes, edges});
  await retry;
  assert.equal(panel.innerHTML, ja);

  lang = "en";
  const englishFailure = loadGraphPanel();
  assert.match(panel.innerHTML, /role="status">Loading graph…/);
  requests[8].reject(new Error("server detail"));
  await englishFailure;
  assert.match(panel.innerHTML, /role="status">Could not load the relationship graph./);
  assert.match(panel.innerHTML, /Reload graph/);
  assert.doesNotMatch(panel.innerHTML, /server detail/);
  const en = renderGraphRelations(nodes, edges);
  const limited = renderGraphRelations(nodes, Array(101).fill(edge));
  console.log(JSON.stringify({ja, en, limited, requested:requests[0].url, empty:renderGraphRelations(nodes, [])}));
})().catch(error => { console.error(error); process.exitCode = 1; });
""",
            ],
            input=json.dumps(_ja_dictionary()),
            capture_output=True,
            text=True,
            timeout=10,
        )
        self.assertEqual(run.returncode, 0, run.stderr)
        result = json.loads(run.stdout)
        self.assertEqual("/api/graph?root=root&depth=2", result["requested"])
        ja = result["ja"]
        en = result["en"]
        self.assertIn("<summary>関係を一覧で表示</summary>", ja)
        self.assertIn("data-no-i18n open>", ja)
        self.assertIn("<svg></svg>", ja)
        self.assertIn(
            "タイトルの全文はノードにマウスを重ねるか、関係一覧で確認できます。", ja
        )
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
