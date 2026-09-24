"""Verify that Core, Cargo metadata, and a Mini binary share one version."""
import argparse, re, subprocess, sys, tomllib
from pathlib import Path

def main() -> int:
    parser=argparse.ArgumentParser(); parser.add_argument('--binary',type=Path); parser.add_argument('--tag'); args=parser.parse_args()
    root=Path(__file__).resolve().parents[1]
    with (root/'pyproject.toml').open('rb') as handle: core=tomllib.load(handle)['project']['version']
    cargo=(root/'lifetxt-mini'/'Cargo.toml').read_text(encoding='utf-8')
    cargo_version=re.search(r'^version\s*=\s*"([^"]+)"',cargo,re.MULTILINE).group(1)
    values={'Core':core,'Cargo':cargo_version}
    if args.binary:
        output=subprocess.check_output([str(args.binary),'--version'],text=True).strip()
        match=re.search(r'\blifetxt-mini\s+(\d+\.\d+\.\d+)\b',output)
        if not match: raise SystemExit(f'cannot parse Mini version from: {output}')
        values['Mini']=match.group(1)
    if len(set(values.values())) != 1: raise SystemExit('version mismatch: '+', '.join(f'{k}={v}' for k,v in values.items()))
    if args.tag and args.tag.removeprefix('v') != core: raise SystemExit(f'tag {args.tag} does not match Core version {core}')
    print('lifetxt-mini version consistent: '+core); return 0
if __name__=='__main__': sys.exit(main())