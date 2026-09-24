"""Run the documented Core/Mini semantic conformance intersection."""
import argparse, json, re, shutil, subprocess, tempfile
from pathlib import Path

SUPPORTED = {"T", "E", "N"}

def records(text):
    result=[]
    for line in text.splitlines():
        m=re.match(r'^\[([ xN])\] ([TEN]) (?:"((?:\\.|[^"\\])*)"|(\S+))(.*)$', line)
        if not m or m.group(2) not in SUPPORTED: continue
        fields=[]
        for token in re.findall(r'(\w+):(\S+|"[^"]*")', m.group(5)):
            fields.append((token[0], token[1].strip('"')))
        result.append({"status":m.group(1),"type":m.group(2),"title":m.group(3) or m.group(4),"fields":fields})
    return result

def ids(rows): return [dict(r["fields"]).get("id") for r in rows if dict(r["fields"]).get("id")]
def run(command, cwd=None): return subprocess.run(command, cwd=cwd, text=True, capture_output=True)
def main():
    p=argparse.ArgumentParser(); p.add_argument("--binary", required=True); p.add_argument("--fixture", type=Path, default=Path("lifetxt-mini/fixtures/mixed-life.txt")); args=p.parse_args()
    root=Path(__file__).resolve().parents[1]; fixture=(root/args.fixture).resolve(); source=fixture.read_text(encoding="utf-8"); expected=records(source); expected_ids=ids(expected)
    core=run(["python","-m","lifetxt","check",str(fixture)],root)
    if core.returncode != 0: raise SystemExit("Core check failed:\n"+core.stderr)
    mini=run([str(Path(args.binary).resolve()),"list",str(fixture)],root)
    if mini.returncode != 0: raise SystemExit("Mini list failed:\n"+mini.stderr)
    listed=[m.group(1) for m in re.finditer(r'\bid:([^\s]+)',mini.stdout)]
    if listed != expected_ids: raise SystemExit(f"list semantic mismatch: expected {expected_ids}, got {listed}")
    for identity in expected_ids:
        shown=run([str(Path(args.binary).resolve()),"show",f"--id={identity}",str(fixture)],root)
        if shown.returncode != 0 or f"id:{identity}" not in shown.stdout: raise SystemExit(f"show failed for {identity}")
    today=run([str(Path(args.binary).resolve()),"today","--date","2026-09-24",str(fixture)],root)
    if today.returncode != 0 or "Mini Runtime Profile" not in today.stdout: raise SystemExit("today lost Mini anti-confusion identity")
    with tempfile.TemporaryDirectory() as directory:
        target=Path(directory)/"life.txt"; shutil.copyfile(fixture,target)
        done=run([str(Path(args.binary).resolve()),"done","--id=t1",str(target)],root)
        if done.returncode != 0: raise SystemExit("done conformance failed: "+done.stderr)
        added=run([str(Path(args.binary).resolve()),"add","Conformance note","--type","note",str(target)],root)
        if added.returncode != 0: raise SystemExit("add conformance failed: "+added.stderr)
        core_after=run(["python","-m","lifetxt","check",str(target)],root)
        if core_after.returncode != 0: raise SystemExit("Core rejected Mini mutation: "+core_after.stderr)
    print(json.dumps({"classification":{"list":"A","show":"A","check":"B","add":"B","done":"B","today":"B"},"core_check":"pass","listed_ids":expected_ids,"mutation_core_check":"pass"},ensure_ascii=False,sort_keys=True))
if __name__ == "__main__": main()
