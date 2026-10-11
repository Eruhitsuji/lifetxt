"""Independent, reviewed public-schema snapshot used by contract tests."""

import hashlib
import json
from pathlib import Path


CONTRACT_PATH = Path(__file__).parent / "fixtures" / "public_schema_contract.json"


def schema_digest(schema):
    encoded = json.dumps(
        schema, sort_keys=True, separators=(",", ":"), ensure_ascii=True
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def load_inventory():
    def unique_object(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("Duplicate contract key: " + key)
            result[key] = value
        return result

    return json.loads(
        CONTRACT_PATH.read_text(encoding="utf-8"), object_pairs_hook=unique_object
    )


def load_contract():
    return load_inventory()["bundle"]


def assert_schema_contract(case, bundle, published, samples, contract=None):
    expected = load_contract() if contract is None else contract
    standalone = load_inventory()["standalone"] if contract is None else {}
    case.assertTrue(expected, "Public schema contract must not be empty")
    case.assertFalse(set(expected) & set(standalone), "Overlapping distributions")
    case.assertEqual(
        set(expected) | set(standalone), set(published), "published schema names"
    )
    for label, values in (("registered", bundle), ("samples", samples)):
        case.assertEqual(set(expected), set(values), label + " schema names")
    for values in (bundle, published):
        identifiers = [schema.get("$id") for schema in values.values()]
        case.assertEqual(len(identifiers), len(set(identifiers)), "Duplicate schema $id")
    for name, entry in expected.items():
        case.assertEqual(entry["$id"], bundle[name].get("$id"), name)
        case.assertEqual(entry["sha256"], schema_digest(bundle[name]), name)
        case.assertEqual(bundle[name], published[name], name)
    for name, entry in standalone.items():
        case.assertEqual(entry["$id"], published[name].get("$id"), name)
        case.assertEqual(entry["sha256"], schema_digest(published[name]), name)


def published_schemas(root):
    return {
        path.name: json.loads(path.read_text(encoding="utf-8"))
        for path in (Path(root) / "dist" / "schemas").glob("*.schema.json")
    }
