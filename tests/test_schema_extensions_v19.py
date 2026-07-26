import unittest
from lifetxt.schema_extensions_v19 import schema_bundle_v19,schema_samples_v19
class SchemaV19Tests(unittest.TestCase):
    def test_six_schemas(self): self.assertEqual(len(schema_bundle_v19()),6)
    def test_samples(self): self.assertEqual(set(schema_bundle_v19()),set(schema_samples_v19()))
