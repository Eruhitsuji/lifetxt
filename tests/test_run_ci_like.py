import importlib.util
import os
import tempfile
import unittest
from unittest import mock


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPT_PATH = os.path.join(ROOT, "scripts", "run_ci_like.py")

_spec = importlib.util.spec_from_file_location("run_ci_like_script", SCRIPT_PATH)
run_ci_like = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(run_ci_like)


class RunCiLikeProfileTests(unittest.TestCase):
    def test_release_profile_runs_only_artifact_specific_validation(self):
        with tempfile.TemporaryDirectory() as root:
            with mock.patch.object(run_ci_like, "_run") as run:
                with mock.patch.object(run_ci_like, "_install_profile_dependencies"):
                    with mock.patch.object(run_ci_like, "_run_tests") as tests:
                        with mock.patch.object(
                            run_ci_like, "_run_examples"
                        ) as examples:
                            with mock.patch.object(
                                run_ci_like, "_run_release_profile"
                            ) as release:
                                run_ci_like.run_for_interpreter(
                                    ["python3.12"],
                                    root,
                                    "release",
                                    False,
                                    True,
                                    False,
                                )

        tests.assert_not_called()
        examples.assert_not_called()
        self.assertEqual(1, release.call_count)
        self.assertEqual(1, run.call_count)
        self.assertEqual(
            ["python3.12", "-m", "venv"],
            run.call_args.args[0][:3],
        )

    def test_non_release_profile_keeps_source_tree_checks(self):
        with tempfile.TemporaryDirectory() as root:
            with mock.patch.object(run_ci_like, "_run") as run:
                with mock.patch.object(run_ci_like, "_install_profile_dependencies"):
                    with mock.patch.object(run_ci_like, "_run_tests") as tests:
                        with mock.patch.object(
                            run_ci_like, "_run_examples"
                        ) as examples:
                            with mock.patch.object(
                                run_ci_like, "_run_release_profile"
                            ) as release:
                                run_ci_like.run_for_interpreter(
                                    ["python3.12"],
                                    root,
                                    "core",
                                    True,
                                    True,
                                    False,
                                )

        self.assertEqual(1, tests.call_count)
        self.assertEqual(1, examples.call_count)
        release.assert_not_called()
        self.assertTrue(
            any(
                call.args[0][-1] == "scripts/smoke_test.py"
                for call in run.call_args_list
            )
        )

    def test_release_profile_does_not_install_optional_web_dependencies(self):
        with mock.patch.object(run_ci_like, "run_for_interpreter") as execute:
            self.assertEqual(
                0,
                run_ci_like.main(["--profile", "release", "--python", "python3.12"]),
            )
        self.assertFalse(execute.call_args.args[3])


if __name__ == "__main__":
    unittest.main()
