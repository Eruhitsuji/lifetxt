"""Exercise the shipped Procedures catalog UI with controlled API responses."""

from importlib import resources
import shutil
import subprocess
import unittest


@unittest.skipUnless(shutil.which("node"), "Node.js unavailable")
class ProcedureCatalogUiTests(unittest.TestCase):
    def test_catalog_guidance_distinguishes_empty_partial_and_failed_loads(self):
        package = resources.files("lifetxt")
        html = package.joinpath("procedure_web.html").read_text(encoding="utf-8")
        for notice in ("catalog-empty", "catalog-partial"):
            self.assertIn(f'id="{notice}" hidden', html)
        script = package.joinpath("procedure_web.js").read_text(encoding="utf-8")
        run_script = package.joinpath("procedure_run_web.js").read_text(
            encoding="utf-8"
        )
        harness = r"""
const assert = require("node:assert/strict");
const nodes = new Map();
const createNode = () => ({
  children: [], dataset: {}, value: "text", hidden: true,
  append(child) { this.children.push(child); },
  replaceChildren() { this.children = []; },
  setAttribute() {}, focus() {},
});
const get = id => {
  if (!nodes.has(id)) nodes.set(id, createNode());
  return nodes.get(id);
};
const document = {
  documentElement: {}, createElement: createNode, getElementById: get,
  querySelectorAll: selector => selector === "[data-text]" ? [
    Object.assign(get("catalog-guide"), {dataset: {text: "guide"}}),
    Object.assign(get("catalog-partial"), {dataset: {text: "unavailable"}}),
  ] : [],
};
const location = {search: "?lang=en"};
const navigator = {language: "en"};
const history = {pushState() {}, replaceState() {}};
const window = {addEventListener() {}};
const empty = {schema: "procedure-catalog-v1", procedures: [], failures: []};
const partial = {...empty, failures: [{message: "private path"}]};
const row = {title: "Example", source: "source", id: "root", href: "/procedures?id=root", valid: true};
const detail = {
  schema: "procedure-v1", mode: "definition", root: {title: row.title, body: []},
  diagnostics: [], steps: [], edges: [], formats: {text: "steps"},
};
// Force the existing diagram fallback so the stub needs no SVG API.
detail.edges.length = 161;
const pending = [];
const fetch = () => new Promise(resolve => pending.push(resolve));
const respond = (data, status = 200) => pending.shift()({ok: status === 200, status, json: async () => data});
const tick = () => new Promise(resolve => setImmediate(resolve));
"""
        assertions = r"""
(async () => {
  respond(empty); await tick();
  assert.equal(get("catalog-empty").hidden, false);
  assert.equal(get("catalog-partial").hidden, true);
  assert.match(get("catalog-guide").href, /docs\/en\/procedure-guidance\.md$/);
  get("language").value = "ja";
  get("language").onchange();
  assert.match(get("catalog-guide").href, /docs\/ja\/procedure-guidance\.md$/);
  assert.equal(get("catalog-guide").textContent, "手順書のガイドを読む");

  let reload = get("reload").onclick();
  assert.equal(get("catalog-empty").hidden, true);
  get("language").value = "en";
  get("language").onchange();
  assert.equal(get("catalog-empty").hidden, true);
  respond(partial); await reload;
  assert.equal(get("catalog-empty").hidden, true);
  assert.equal(get("catalog-partial").hidden, false);

  reload = get("reload").onclick();
  assert.equal(get("catalog-partial").hidden, true);
  respond({...partial, procedures: [row]}); await reload;
  const link = get("catalog").children[0].children[0];
  link.onclick({preventDefault() {}});
  respond(detail); await tick();
  assert.equal(get("definition").hidden, false);
  assert.equal(get("catalog-partial").hidden, false);

  reload = get("reload").onclick();
  respond({}, 503); await reload;
  assert.equal(get("catalog-empty").hidden, true);
  assert.equal(get("catalog-partial").hidden, true);
  assert.match(get("feedback").textContent, /Could not load/);
  console.log("passed");
})().catch(error => { console.error(error); process.exitCode = 1; });
"""
        result = subprocess.run(
            ["node", "-"],
            input=harness
            + script.replace("__PROCEDURE_RUN_JS__", run_script)
            + assertions,
            capture_output=True,
            text=True,
            timeout=15,
        )
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual("passed", result.stdout.strip())
