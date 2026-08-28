"""Docker image contract tests.

Two tiers: cheap, always-run static checks over Dockerfile/.dockerignore/
docker-compose.yml, and a slower, docker-gated build+run smoke test that
skips with a diagnostic reason when Docker is unavailable (matching this
project's established pattern for environment-dependent suites) rather than
failing or silently passing.
"""

from __future__ import annotations

import shutil
import subprocess
import time
import unittest
import urllib.error
import urllib.request
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
DOCKERFILE = REPO_ROOT / "Dockerfile"
COMPOSE_FILE = REPO_ROOT / "docker-compose.yml"
DOCKERIGNORE = REPO_ROOT / ".dockerignore"


def _docker_available():
    if shutil.which("docker") is None:
        return False, "docker executable not found on PATH"
    try:
        result = subprocess.run(
            ["docker", "info"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=10,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return False, "docker info failed: %s" % exc
    if result.returncode != 0:
        return False, "docker daemon unreachable (docker info exited non-zero)"
    return True, ""


class DockerfileStaticContractTests(unittest.TestCase):
    def setUp(self):
        self.text = DOCKERFILE.read_text(encoding="utf-8")

    def test_entrypoint_maps_directly_onto_the_cli(self):
        self.assertIn('ENTRYPOINT ["lifetxt"]', self.text)

    def test_two_stage_build_keeps_build_tooling_out_of_the_runtime_layer(self):
        self.assertIn("AS build", self.text)
        self.assertIn("COPY --from=build", self.text)
        self.assertNotIn(
            "RUN pip install --no-cache-dir --upgrade pip build",
            self.text.split("FROM", 2)[-1],
        )

    def test_runs_as_a_non_root_user(self):
        self.assertIn("USER lifetxt", self.text)
        self.assertIn("useradd", self.text)

    def test_declares_a_data_volume_and_web_port(self):
        self.assertIn('VOLUME ["/data"]', self.text)
        self.assertIn("EXPOSE 8000", self.text)

    def test_wheel_extras_are_resolved_through_a_shell_variable(self):
        # Regression guard: `pip install /tmp/*.whl[web]` is silently
        # misparsed by the shell (the `[web]` glob character class matches
        # no file), which this project's own local build reproduced and
        # fixed before this test was written. Only actual instruction lines
        # are checked, since the fix's own explanatory comment necessarily
        # quotes the broken form.
        code_lines = [
            line
            for line in self.text.splitlines()
            if line.strip() and not line.strip().startswith("#")
        ]
        self.assertFalse(any("*.whl[web]" in line for line in code_lines))
        self.assertIn('"${WHEEL_FILE}[web]"', self.text)


class DockerignoreTests(unittest.TestCase):
    def test_dockerignore_is_tracked_despite_the_leading_dot_gitignore_rule(self):
        gitignore = (REPO_ROOT / ".gitignore").read_text(encoding="utf-8")
        self.assertIn("!.dockerignore", gitignore)

    def test_dockerignore_excludes_the_git_directory_and_virtualenvs(self):
        text = DOCKERIGNORE.read_text(encoding="utf-8")
        self.assertIn(".git", text)
        self.assertIn(".venv", text)


class ComposeFileStaticContractTests(unittest.TestCase):
    def setUp(self):
        self.text = COMPOSE_FILE.read_text(encoding="utf-8")

    def test_references_the_ghcr_image(self):
        self.assertIn("ghcr.io/eruhitsuji/lifetxt", self.text)

    def test_requires_an_api_token_rather_than_defaulting_one_in(self):
        self.assertIn("LIFETXT_API_TOKEN", self.text)
        self.assertIn(":?", self.text)  # compose "required, error if unset" syntax

    def test_env_example_file_exists_and_is_tracked(self):
        env_example = REPO_ROOT / "docker-compose.env.example"
        self.assertTrue(env_example.exists())
        result = subprocess.run(
            ["git", "check-ignore", "-q", str(env_example)],
            cwd=str(REPO_ROOT),
        )
        self.assertNotEqual(
            result.returncode, 0, "docker-compose.env.example must not be gitignored"
        )


@unittest.skipUnless(*_docker_available())
class DockerImageBuildAndRunTests(unittest.TestCase):
    IMAGE_TAG = "lifetxt:test-docker-image-suite"

    @classmethod
    def setUpClass(cls):
        subprocess.run(
            ["docker", "build", "-t", cls.IMAGE_TAG, "."],
            cwd=str(REPO_ROOT),
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

    @classmethod
    def tearDownClass(cls):
        subprocess.run(
            ["docker", "image", "rm", "-f", cls.IMAGE_TAG],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

    def test_version_flag(self):
        result = subprocess.run(
            ["docker", "run", "--rm", self.IMAGE_TAG, "--version"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(result.stdout.strip().startswith("lifetxt "))

    def test_runs_as_uid_1000(self):
        result = subprocess.run(
            ["docker", "run", "--rm", "--entrypoint", "id", self.IMAGE_TAG],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("uid=1000(lifetxt)", result.stdout)

    def test_check_command_against_a_mounted_example(self):
        result = subprocess.run(
            [
                "docker",
                "run",
                "--rm",
                "-v",
                "%s/examples:/data" % REPO_ROOT,
                self.IMAGE_TAG,
                "check",
                "/data/minimal_life.txt",
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("OK", result.stdout)

    def test_serve_mode_answers_health_check(self):
        container = "lifetxt-test-docker-image-suite-serve"
        subprocess.run(
            ["docker", "rm", "-f", container],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        try:
            run = subprocess.run(
                [
                    "docker",
                    "run",
                    "-d",
                    "--name",
                    container,
                    "-p",
                    "18322:8000",
                    "-v",
                    "%s/examples:/data" % REPO_ROOT,
                    self.IMAGE_TAG,
                    "serve",
                    "/data/minimal_life.txt",
                    "--host",
                    "0.0.0.0",
                    "--port",
                    "8000",
                    "--read-only",
                ],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            self.assertEqual(run.returncode, 0, run.stderr)

            body = None
            for _ in range(20):
                try:
                    with urllib.request.urlopen(
                        "http://127.0.0.1:18322/api/health", timeout=1
                    ) as response:
                        body = response.read()
                        break
                except (urllib.error.URLError, ConnectionError):
                    time.sleep(0.5)
            self.assertIsNotNone(body, "container never answered /api/health")
            self.assertIn(b'"ok":true', body)
        finally:
            subprocess.run(
                ["docker", "rm", "-f", container],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )


if __name__ == "__main__":
    unittest.main()
