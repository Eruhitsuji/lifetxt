import importlib.util
import os
import unittest


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPT_PATH = os.path.join(ROOT, "scripts", "check_release_policy.py")

_spec = importlib.util.spec_from_file_location(
    "check_release_policy_script", SCRIPT_PATH
)
check_release_policy = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(check_release_policy)


class _FakeConsoleStream:
    """Mimics a real TextIOWrapper: raises UnicodeEncodeError like a narrow console codec."""

    def __init__(self, encoding):
        self.encoding = encoding
        self.written = []

    def write(self, text):
        text.encode(self.encoding)
        self.written.append(text)
        return len(text)


class WriteStdoutFallbackTests(unittest.TestCase):
    def test_utf8_stream_receives_text_unchanged(self):
        stream = _FakeConsoleStream("utf-8")
        check_release_policy._write_stdout(stream, "note ↵ end\n")
        self.assertEqual(stream.written, ["note ↵ end\n"])

    def test_narrow_codec_stream_falls_back_instead_of_raising(self):
        stream = _FakeConsoleStream("cp932")
        check_release_policy._write_stdout(stream, "note ↵ end\n")
        self.assertEqual(len(stream.written), 1)
        written = stream.written[0]
        self.assertNotIn("↵", written)
        self.assertIn("note ", written)
        self.assertIn(" end\n", written)

    def test_narrow_codec_stream_leaves_encodable_text_unchanged(self):
        stream = _FakeConsoleStream("cp932")
        check_release_policy._write_stdout(stream, "plain ascii text\n")
        self.assertEqual(stream.written, ["plain ascii text\n"])


if __name__ == "__main__":
    unittest.main()
