import copy
from pathlib import Path
import unittest

from lifetxt import bootstrap_legacy_surfaces

bootstrap_legacy_surfaces()

from lifetxt import release_policy
from lifetxt.safety_foundation import schema_bundle
from tests.schema_contract import (
    assert_schema_contract,
    load_contract,
    published_schemas,
    schema_digest,
)


class PublicSchemaContractTests(unittest.TestCase):
    def test_registered_published_and_sample_sets_match_reviewed_contract(self):
        assert_schema_contract(
            self,
            schema_bundle(),
            published_schemas(Path(__file__).parent.parent),
            release_policy._schema_samples(),
        )

    def test_negative_fixtures_reject_contract_drift(self):
        original = {
            "alpha-v1.schema.json": {"$id": "urn:alpha:v1", "type": "string"},
            "beta-v1.schema.json": {"$id": "urn:beta:v1", "type": "integer"},
        }
        contract = {
            name: {"$id": value["$id"], "sha256": schema_digest(value)}
            for name, value in original.items()
        }
        for mutation in (
            "add",
            "delete",
            "replace",
            "duplicate-id",
            "changed-id",
            "synchronized-content",
            "missing-published",
            "extra-published",
            "published-content",
            "missing-sample",
        ):
            with self.subTest(mutation=mutation):
                bundle = copy.deepcopy(original)
                published = copy.deepcopy(original)
                samples = dict.fromkeys(original)
                if mutation == "add":
                    bundle["gamma-v1.schema.json"] = {"$id": "urn:gamma:v1"}
                elif mutation == "delete":
                    del bundle["alpha-v1.schema.json"]
                elif mutation == "replace":
                    bundle["gamma-v1.schema.json"] = bundle.pop("alpha-v1.schema.json")
                elif mutation == "duplicate-id":
                    bundle["beta-v1.schema.json"]["$id"] = "urn:alpha:v1"
                elif mutation == "changed-id":
                    bundle["alpha-v1.schema.json"]["$id"] = "urn:alpha:v2"
                elif mutation == "synchronized-content":
                    bundle["alpha-v1.schema.json"]["type"] = "boolean"
                    published = copy.deepcopy(bundle)
                elif mutation == "missing-published":
                    del published["alpha-v1.schema.json"]
                elif mutation == "extra-published":
                    published["gamma-v1.schema.json"] = {"$id": "urn:gamma:v1"}
                elif mutation == "published-content":
                    published["alpha-v1.schema.json"]["type"] = "boolean"
                else:
                    del samples["alpha-v1.schema.json"]
                with self.assertRaises(AssertionError):
                    assert_schema_contract(self, bundle, published, samples, contract)

    def test_contract_is_nonempty_and_schema_ids_are_unique(self):
        contract = load_contract()
        self.assertTrue(contract)
        ids = [entry["$id"] for entry in contract.values()]
        self.assertEqual(len(ids), len(set(ids)))


if __name__ == "__main__":
    unittest.main()
