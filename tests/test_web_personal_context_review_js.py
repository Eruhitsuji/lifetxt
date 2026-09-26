"""Behavioral coverage for Personal Context review-outcome JS (#960/#961)."""

import json
import re
import shutil
import subprocess
import unittest

from lifetxt.web_assets import HTML_PAGE


def _script_block():
    match = re.search(r"<script>(.*)</script>", HTML_PAGE, re.S)
    assert match is not None
    script = match.group(1)
    start = script.index("function personalContextSourceRevision")
    end = script.index("async function loadMorePersonalContext", start)
    renderer_start = script.index("function personalContextTags")
    return script[renderer_start:end]


_HARNESS = r"""
%s

// ── Minimal DOM/runtime stub, matching the established Node harness
// pattern used by tests.test_web_quick_status_js. ──
const state = {
  current: {
    setAttribute: () => {},
    _menus: [],
    querySelectorAll: selector => selector.includes("[open]")
      ? state.current._menus.filter(menu => menu.open) : state.current._menus,
    set innerHTML(html) {
      this._html = html;
      this._menus = [...html.matchAll(/<details class="personal-context-review-menu" data-personal-context-id="([^"]+)"/g)]
        .map(match => ({dataset: {personalContextId: match[1]}, open: false}));
    },
    get innerHTML() { return this._html || ""; },
    dataset: {
      personalContextItems: "[]",
      personalContextOffset: "0",
      personalContextSourceRevision: "",
    },
  },
  includeStale: {checked: false},
};
global.document = {
  getElementById: id => {
    if (id === "personal-context-current") return state.current;
    if (id === "personal-context-include-stale") return state.includeStale;
    if (id === "personal-context-feedback") return state.feedback || (state.feedback = {textContent: ""});
    return null;
  },
};
global.window = {scrollY: 0, scrollTo: (_x, y) => { global.window.scrollY = y; }};
const t = value => value;
const escapeHtml = value => String(value);
let personalContextReadOnly = false;
const personalContextSelectedIds = new Set();
const PERSONAL_CONTEXT_DOMAINS = ["profile", "preference", "skill", "goal", "project"];
const PERSONAL_CONTEXT_LABELS = {profile: "Profile", preference: "Preferences", skill: "Skills", goal: "Goals", project: "Projects"};

let apiCalls = [];
let apiImpl = null;
const api = async (path, options) => {
  apiCalls.push({path, options});
  return apiImpl(path, options);
};

function fakePage(offset, limit, total) {
  const items = [];
  for (let i = offset; i < Math.min(offset + limit, total); i += 1) {
    items.push({id: `item${i}`, title: `Item ${i}`, stale: false, details: {}});
  }
  return {
    schema: "personal-context-capsule-v1",
    items,
    offset,
    count: items.length,
    total_count: total,
    has_more: offset + items.length < total,
    source_revision: `rev-${total}`,
    currentness_counts: {current: total, stale: 0},
  };
}


async function main() {
  const results = {};

  // 1. A single page (<=100 loaded) refetches exactly that page, not the
  //    default page-1-only shape, and starts offset back at 0.
  state.current.dataset.personalContextItems = JSON.stringify(
    fakePage(0, 40, 40).items
  );
  apiCalls = [];
  apiImpl = async (path) => {
    const match = /offset=(\d+)/.exec(path);
    const offset = match ? Number(match[1]) : 0;
    return fakePage(offset, 100, 40);
  };
  const small = await refreshLoadedPersonalContext();
  results.small_page_calls = apiCalls.length;
  results.small_page_items = small.items.length;
  results.small_page_offset = state.current.dataset.personalContextOffset;

  // 2. A range spanning more than one 100-record server page (as produced
  //    by two Load more clicks) is refetched in full, not reset to the
  //    first page -- the actual #961 regression.
  state.current.dataset.personalContextItems = JSON.stringify(
    fakePage(0, 250, 250).items
  );
  apiCalls = [];
  apiImpl = async (path) => {
    const match = /offset=(\d+)/.exec(path);
    const offset = match ? Number(match[1]) : 0;
    return fakePage(offset, 100, 250);
  };
  const large = await refreshLoadedPersonalContext();
  results.large_page_calls = apiCalls.length;
  results.large_page_items = large.items.length;
  results.large_page_has_more = large.has_more;
  results.large_page_ids = large.items.map(row => row.id);

  // 3. include_stale is preserved across the refresh.
  state.includeStale.checked = true;
  state.current.dataset.personalContextItems = JSON.stringify(fakePage(0, 10, 10).items);
  apiCalls = [];
  apiImpl = async () => fakePage(0, 10, 10);
  await refreshLoadedPersonalContext();
  results.include_stale_forwarded = apiCalls.every(call => call.path.includes("include_stale=true"));
  state.includeStale.checked = false;

  // 4. Scroll position is restored after the refresh (never reset to top
  //    just because a review action ran).
  global.window.scrollY = 842;
  state.current.dataset.personalContextItems = JSON.stringify(fakePage(0, 10, 10).items);
  apiImpl = async () => fakePage(0, 10, 10);
  await refreshLoadedPersonalContext();
  results.scroll_restored = global.window.scrollY;

  // 5. reconfirmPersonalContext/expirePersonalContext/correctPersonalContext
  //    all call the shared refresh, never the full-reset loadPersonalContext.
  apiCalls = [];
  apiImpl = async (path) => {
    if (path.includes("/reconfirm")) return {id: "item1", reconfirmed: true};
    return fakePage(0, 10, 10);
  };
  state.current.dataset.personalContextItems = JSON.stringify(fakePage(0, 10, 10).items);
  await reconfirmPersonalContext("item1");
  results.reconfirm_refreshed = apiCalls.some(call => call.path.startsWith("/api/personal-context?"));
  results.reconfirm_feedback = state.feedback.textContent;

  apiCalls = [];
  apiImpl = async (path) => {
    if (path.includes("/expire")) return {id: "item1", state: "expired"};
    return fakePage(0, 10, 10);
  };
  await expirePersonalContext("item1");
  results.expire_feedback = state.feedback.textContent;
  results.expire_called_expire_route = apiCalls.some(call => call.path.includes("/expire"));

  // Expanded menu state follows stable IDs after an authoritative refresh.
  state.current.dataset.personalContextItems = JSON.stringify(fakePage(0, 3, 3).items);
  renderPersonalContextCurrent(fakePage(0, 3, 3));
  state.current._menus.find(menu => menu.dataset.personalContextId === "item0").open = true;
  apiImpl = async path => path.includes("/reconfirm") ? {id: "item1", reconfirmed: true} : ({...fakePage(0, 3, 3), items: [
    {id: "item2", title: "C", details: {}},
    {id: "item0", title: "A", details: {}},
    {id: "item1", title: "B", details: {}},
  ]});
  await reconfirmPersonalContext("item1");
  results.open_menu_after_reorder = state.current._menus.filter(menu => menu.open).map(menu => menu.dataset.personalContextId);
  apiImpl = async () => ({...fakePage(0, 2, 2), items: [
    {id: "item2", title: "C", details: {}},
    {id: "item1", title: "B", details: {}},
  ]});
  await refreshLoadedPersonalContext();
  results.open_menu_after_removal = state.current._menus.filter(menu => menu.open).map(menu => menu.dataset.personalContextId);
  personalContextReadOnly = true;
  renderPersonalContextCurrent({...fakePage(0, 1, 1), items: [{id: "item1", title: "B", stale: true, details: {}}]});
  results.read_only_no_mutation_controls = !state.current.innerHTML.includes("Still correct") && !state.current.innerHTML.includes("personal-context-review-menu") && !state.current.innerHTML.includes("data-personal-context-select");
  personalContextReadOnly = false;
  return results;
}

main().then(results => console.log(JSON.stringify(results))).catch(error => {
  console.error(error);
  process.exit(1);
});
"""


@unittest.skipUnless(shutil.which("node"), "node is not on PATH")
class PersonalContextReviewJsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        proc = subprocess.run(
            ["node", "-e", _HARNESS % _script_block()],
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=30,
        )
        if proc.returncode != 0:
            raise AssertionError(proc.stderr or proc.stdout)
        cls.results = json.loads(proc.stdout)

    def test_open_menu_tracks_record_id_and_disappeared_records_are_ignored(self):
        self.assertEqual(["item0"], self.results["open_menu_after_reorder"])
        self.assertEqual([], self.results["open_menu_after_removal"])

    def test_read_only_renderer_hides_review_mutations(self):
        self.assertTrue(self.results["read_only_no_mutation_controls"])

    def test_small_loaded_range_is_refetched_as_one_page(self):
        self.assertEqual(1, self.results["small_page_calls"])
        self.assertEqual(40, self.results["small_page_items"])
        self.assertEqual("0", self.results["small_page_offset"])

    def test_multi_page_loaded_range_is_refetched_in_full_not_reset(self):
        # 250 previously-loaded records span three server pages (100+100+50).
        self.assertEqual(3, self.results["large_page_calls"])
        self.assertEqual(250, self.results["large_page_items"])
        self.assertFalse(self.results["large_page_has_more"])
        self.assertEqual(
            [f"item{i}" for i in range(250)], self.results["large_page_ids"]
        )

    def test_include_stale_filter_is_preserved_across_the_refresh(self):
        self.assertTrue(self.results["include_stale_forwarded"])

    def test_scroll_position_is_restored_after_refresh(self):
        self.assertEqual(842, self.results["scroll_restored"])

    def test_reconfirm_uses_the_shared_range_preserving_refresh(self):
        self.assertTrue(self.results["reconfirm_refreshed"])
        self.assertEqual("Reconfirmed.", self.results["reconfirm_feedback"])

    def test_expire_calls_the_expire_route_and_reports_feedback(self):
        self.assertTrue(self.results["expire_called_expire_route"])
        self.assertEqual("No longer valid.", self.results["expire_feedback"])


if __name__ == "__main__":
    unittest.main()
