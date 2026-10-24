"""Non-public Windows editor artifact producer; no release or installation authority."""

import argparse
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path
from xml.etree import ElementTree

import release_preflight_core as core
import release_preflight_proof as proof

TARGET = "editor-windows"
VSCE_VERSION = "3.7.1"
METADATA = "lifetxt-editor-release-v1"
ROLES = {"vsix", "neovim-config"}
CHECKS = {"vsix-package", "neovim-config", "provenance", "offline"}
REPORT_FIELDS = {
    "schema_version", "candidate_digest", "source_sha", "controller_sha",
    "run_id", "run_attempt", "target", "observed_version", "editor_version",
    "toolchain", "checks", "files",
}
INSTALL = """# Windows Neovim 0.11+ (nvim) / Windows Neovim 0.11+ 導入

1. Install Neovim and separately install lifetxt in Python 3.10+:
   py -3.12 -m pip install lifetxt
2. Extract this archive to a trusted local directory. Review lifetxt.lua.
3. In init.lua, explicitly load the extracted file with:
   dofile([[C:\\path\\to\\lifetxt.lua]])
4. Set the 'python' executable in lifetxt.lua's cmd to the Python
   interpreter containing lifetxt. Reload Neovim and open life.txt.
5. For weekly .txt files explicitly run :setfiletype lifetxt.
6. Disable LSP with :lua vim.lsp.enable('lifetxt', false).
   Remove the dofile line and files to uninstall.

日本語: Pythonのlifetxt導入は明示的な操作です。Luaの読み込みを
init.luaに追記し、cmd内のpythonを導入先に変更してください。
停止は :lua vim.lsp.enable('lifetxt', false)。
元に戻すときはdofile行を削除し、展開したファイルを削除します。
Python/LSPがなくても通常の手動テキスト編集は利用できます。
通常Vim/Vim9とWindows以外の動作保証は対象外です。
"""


def names(candidate):
    version = candidate["version"]
    return {
        "lifetxt-vscode-" + version + ".vsix": "vsix",
        "lifetxt-neovim-windows-" + version + ".zip": "neovim-config",
    }


def metadata(candidate, editor_version):
    return {
        "schema": METADATA,
        "source_sha": candidate["source_sha"],
        "release_version": candidate["version"],
        "candidate_digest": candidate["digest"],
        "editor_version": editor_version,
    }


def checked_archive(path, *, max_size=80 * 1024 * 1024):
    proof.require(path.is_file() and not path.is_symlink(), "missing editor archive")
    proof.require(path.stat().st_size <= max_size, "oversized editor archive")
    with zipfile.ZipFile(path) as archive:
        names_seen = set()
        rows = {}
        total = 0
        for info in archive.infolist():
            key = info.filename
            parts = key.rstrip("/").split("/")
            proof.require(
                key and "\\" not in key and not key.startswith("/")
                and all(part not in ("", ".", "..") for part in parts)
                and "\x00" not in key and not (info.external_attr >> 16 & 0o170000) == 0o120000,
                "unsafe editor archive entry",
            )
            folded = key.rstrip("/").casefold()
            proof.require(folded not in names_seen, "duplicate editor archive entry")
            names_seen.add(folded)
            total += info.file_size
            proof.require(total <= max_size and info.file_size <= max_size, "editor archive expands too far")
            if not info.is_dir():
                rows[key] = archive.read(key)
        return rows


def smoke_vsix(candidate, path):
    rows = checked_archive(path)
    required = {
        "[Content_Types].xml", "extension.vsixmanifest",
        "extension/package.json", "extension/release.json",
        "extension/extension.js", "extension/language-configuration.json",
        "extension/syntaxes/lifetxt.tmLanguage.json",
        "extension/snippets/lifetxt.code-snippets",
        "extension/node_modules/vscode-languageclient/package.json",
        "extension/node_modules/vscode-languageclient/node.js",
        "extension/node_modules/vscode-languageclient/lib/node/main.js",
    }
    proof.require(required <= set(rows), "VSIX missing language/client content")
    manifest = json.loads(rows["extension/package.json"])
    version = manifest["version"]
    proof.require(
        re.fullmatch(r"(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)", version),
        "invalid independent VS Code SemVer",
    )
    proof.require(
        manifest["name"] == "lifetxt" and manifest["main"] == "./extension.js"
        and manifest["contributes"]["languages"][0]["id"] == "lifetxt"
        and manifest["contributes"]["configuration"]["properties"]["lifetxt.languageServer.enabled"]["default"] is False,
        "VSIX manifest semantics changed",
    )
    identity = [
        element for element in ElementTree.fromstring(rows["extension.vsixmanifest"]).iter()
        if element.tag.rsplit("}", 1)[-1] == "Identity"
    ]
    proof.require(
        len(identity) == 1 and identity[0].get("Version") == version,
        "VSIX identity/version mismatch",
    )
    proof.require(
        json.loads(rows["extension/release.json"]) == metadata(candidate, version),
        "VSIX provenance mismatch",
    )
    client = json.loads(rows["extension/node_modules/vscode-languageclient/package.json"])
    proof.require(
        client.get("name") == "vscode-languageclient"
        and client.get("version") == manifest.get("optionalDependencies", {}).get("vscode-languageclient"),
        "VSIX optional client version mismatch",
    )
    proof.require(
        rows["extension/node_modules/vscode-languageclient/node.js"]
        and rows["extension/node_modules/vscode-languageclient/lib/node/main.js"],
        "VSIX optional client entry is empty",
    )
    for name in ("extension/syntaxes/lifetxt.tmLanguage.json",
                 "extension/snippets/lifetxt.code-snippets",
                 "extension/language-configuration.json",
                 "extension/node_modules/vscode-languageclient/package.json"):
        json.loads(rows[name])
    proof.require(rows["extension/extension.js"], "empty VS Code entry")
    return version


def smoke_neovim(candidate, path, editor_version):
    rows = checked_archive(path)
    proof.require(
        set(rows) == {"lifetxt.lua", "INSTALL-WINDOWS.md", "release.json"},
        "Neovim bundle inventory mismatch",
    )
    proof.require(
        json.loads(rows["release.json"]) == metadata(candidate, editor_version),
        "Neovim provenance mismatch",
    )
    lua = rows["lifetxt.lua"].decode("utf-8")
    proof.require(
        "vim.lsp.config('lifetxt'" in lua and "vim.lsp.enable('lifetxt')" in lua
        and "'lifetxt.lsp', '--stdio'" in lua
        and "vim.filetype.add" in lua and "vim.lsp.enable" in lua,
        "Neovim built-in LSP configuration missing",
    )
    guide = rows["INSTALL-WINDOWS.md"].decode("utf-8")
    proof.require("init.lua" in guide and "disable" in guide.lower()
                  and "Python" in guide and "Windows" in guide,
                  "Neovim Windows install/recovery instructions missing")


def validate_payload(candidate, payload):
    proof.validate_candidate(candidate)
    payload = Path(payload)
    expected = names(candidate)
    proof.require(
        payload.is_dir()
        and {p.name for p in payload.iterdir()} == set(expected)
        and all(p.is_file() and not p.is_symlink() for p in payload.iterdir()),
        "editor payload missing/extra files",
    )
    vsix = payload / next(name for name, role in expected.items() if role == "vsix")
    nvim = payload / next(name for name, role in expected.items() if role == "neovim-config")
    version = smoke_vsix(candidate, vsix)
    smoke_neovim(candidate, nvim, version)
    return version


def build(candidate, controller, source, payload, report, context):
    controller, source, payload, report = map(
        lambda p: Path(p).resolve(), (controller, source, payload, report)
    )
    core.validate_context(candidate, controller, context)
    core.validate_source(candidate, source)
    proof.require(not payload.exists() and not report.exists(), "editor build output exists")
    extension = source / "editors/vscode/lifetxt"
    package = json.loads((extension / "package.json").read_text(encoding="utf-8"))
    proof.require(package["optionalDependencies"]["vscode-languageclient"], "missing client dependency")
    with tempfile.TemporaryDirectory(prefix="lifetxt-editor-build-") as tmp:
        staged = Path(tmp) / "extension"
        shutil.copytree(extension, staged, ignore=shutil.ignore_patterns("node_modules", ".git"))
        (staged / "release.json").write_text(
            json.dumps(metadata(candidate, package["version"]), sort_keys=True) + "\n",
            encoding="utf-8",
        )
        # Network access is confined to explicit build dependencies; no script execution.
        # vsce must walk npm production dependencies; --no-dependencies would
        # omit the unbundled optional vscode-languageclient from the VSIX.
        subprocess.run(
            ["npm", "ci", "--omit=dev", "--ignore-scripts", "--no-audit", "--no-fund"],
            cwd=staged, check=True, timeout=300,
        )
        payload.mkdir(parents=True)
        vsix = payload / next(n for n, role in names(candidate).items() if role == "vsix")
        subprocess.run(
            ["npx", "--yes", "--package=@vscode/vsce@" + VSCE_VERSION, "vsce",
             "package", "--allow-missing-repository", "--out", str(vsix)],
            cwd=staged, check=True, timeout=300,
        )
        nvim = payload / next(n for n, role in names(candidate).items() if role == "neovim-config")
        with zipfile.ZipFile(nvim, "w", zipfile.ZIP_DEFLATED) as out:
            out.write(source / "editors/neovim/lifetxt.lua", "lifetxt.lua")
            out.writestr("INSTALL-WINDOWS.md", INSTALL)
            out.writestr("release.json", json.dumps(metadata(candidate, package["version"]), sort_keys=True) + "\n")
    version = validate_payload(candidate, payload)
    core.validate_source(candidate, source)
    core.validate_context(candidate, controller, context)
    report_data = proof.sealed({
        "schema_version": 1,
        "candidate_digest": candidate["digest"],
        **{k: candidate[k] for k in ("source_sha", "controller_sha", "run_id", "run_attempt")},
        "target": TARGET, "observed_version": candidate["version"], "editor_version": version,
        "toolchain": {"python": platform.python_version(), "runner": platform.platform(),
                      "vsce": VSCE_VERSION},
        "checks": dict.fromkeys(CHECKS, "passed"),
        "files": [
            {"path": name, "role": role,
             "sha256": proof.file_digest(payload / name), "bytes": (payload / name).stat().st_size}
            for name, role in sorted(names(candidate).items())
        ],
    })
    proof.write_new(report, report_data)
    return report_data


def finish(candidate, report, payload, artifact, target=TARGET):
    proof.require(target == TARGET, "wrong editor target")
    row = proof.unseal(report, REPORT_FIELDS, "Editor report")
    proof.require(row["schema_version"] == 1, "unsupported Editor report schema")
    for key in ("candidate_digest", "source_sha", "controller_sha", "run_id", "run_attempt"):
        expected = candidate["digest"] if key == "candidate_digest" else candidate[key]
        proof.require(type(row[key]) is type(expected) and row[key] == expected, "Editor report identity mismatch")
    version = validate_payload(candidate, payload)
    proof.require(row["editor_version"] == version, "Editor version changed")
    proof.require(
        row["target"] == TARGET and row["observed_version"] == candidate["version"]
        and row["checks"] == dict.fromkeys(CHECKS, "passed"),
        "Editor smoke report mismatch",
    )
    expected = names(candidate)
    proof.require(
        {(r["path"], r["role"]) for r in row["files"]} == set(expected.items()),
        "Editor role/name mismatch",
    )
    spec = {
        "target": target, "artifact": artifact, "observed_version": row["observed_version"],
        "toolchain": row["toolchain"], "checks": row["checks"], "oci_digest": None,
        "files": [{"path": r["path"], "role": r["role"]} for r in row["files"]],
    }
    component = proof.component(candidate, spec, payload)
    proof.require(component["files"] == row["files"], "Editor bytes changed after smoke")
    return component


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    cmd = parser.add_subparsers(dest="command", required=True)
    for name in ("build", "component"):
        part = cmd.add_parser(name)
        for option in ("candidate", "controller", "source", "payload", "report"):
            part.add_argument("--" + option, required=True, type=Path)
        if name == "component":
            part.add_argument("--artifact-id", required=True, type=int)
            part.add_argument("--artifact-name", required=True)
            part.add_argument("--artifact-digest", required=True)
            part.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        candidate = proof.load(args.candidate)
        if args.command == "build":
            build(candidate, args.controller, args.source, args.payload, args.report, os.environ)
        else:
            core.validate_context(candidate, args.controller, os.environ)
            core.validate_source(candidate, args.source)
            result = finish(candidate, proof.load(args.report), args.payload, {
                "id": args.artifact_id, "name": args.artifact_name, "sha256": args.artifact_digest
            })
            proof.write_new(args.output, result)
    except (ValueError, OSError, KeyError, TypeError, subprocess.SubprocessError, zipfile.BadZipFile, ElementTree.ParseError) as exc:
        parser.exit(1, "Editor preflight rejected: %s\n" % exc)
    return 0


if __name__ == "__main__":
    sys.exit(main())
