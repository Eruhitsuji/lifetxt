"""Legacy consumer snapshots must match initialized registries in fresh processes."""

import json
import subprocess
import sys
import unittest
from pathlib import Path


class McpImportOrderTests(unittest.TestCase):
    def test_consumer_and_bootstrap_permutations_have_identical_registries(self):
        setup_orders = (
            "import tests.test_mcp_expansion as consumer",
            "import lifetxt; lifetxt.bootstrap_legacy_surfaces(); import tests.test_mcp_expansion as consumer",
            "import lifetxt.mcp; import tests.test_mcp_expansion as consumer",
        )
        snapshots = []
        for setup in setup_orders:
            with self.subTest(setup=setup):
                script = (
                    setup
                    + """
import json
import lifetxt.mcp as mcp
assert consumer.READ_ONLY_TOOLS is mcp.READ_ONLY_TOOLS
assert consumer.tool_schemas is mcp.tool_schemas
assert consumer.call_tool is mcp.call_tool
schemas = mcp.tool_schemas()
assert {schema['name'] for schema in schemas} == set(mcp.TOOL_HANDLERS)
assert all(schema['annotations']['readOnlyHint'] == (schema['name'] in mcp.READ_ONLY_TOOLS) for schema in schemas)
print(json.dumps({'read': sorted(mcp.READ_ONLY_TOOLS), 'schemas': sorted(schema['name'] for schema in schemas)}))
"""
                )
                result = subprocess.run(
                    [sys.executable, "-c", script],
                    cwd=Path(__file__).resolve().parents[1],
                    capture_output=True,
                    text=True,
                    timeout=30,
                )
                self.assertEqual(0, result.returncode, result.stderr)
                snapshots.append(json.loads(result.stdout))
        self.assertTrue(all(snapshot == snapshots[0] for snapshot in snapshots[1:]))
