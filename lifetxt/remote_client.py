"""Dependency-free Remote Safe Mode client and profile store."""
from __future__ import unicode_literals
import argparse, json, os, stat, sys
from collections import OrderedDict
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

PROFILE_VERSION=2

def profile_path(path=None): return os.path.abspath(os.path.expanduser(path or os.environ.get("LIFETXT_REMOTE_PROFILES") or "~/.config/lifetxt/remote-profiles.json"))
def _load(path=None):
    p=profile_path(path)
    if not os.path.exists(p): return {"version":PROFILE_VERSION,"profiles":{}}
    with open(p,encoding="utf-8") as h: data=json.load(h)
    data.setdefault("version",PROFILE_VERSION); data.setdefault("profiles",{}); return data

def _save(data,path=None):
    p=profile_path(path); os.makedirs(os.path.dirname(p),exist_ok=True)
    from .atomic import atomic_write_text
    atomic_write_text(p,json.dumps(data,ensure_ascii=False,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    try: os.chmod(p,stat.S_IRUSR|stat.S_IWUSR)
    except OSError: pass
    return p

def set_profile(name,url,token_env=None,verify_tls=True,path=None):
    if str(url).startswith("http://") and not any(x in str(url) for x in ("127.0.0.1","localhost","[::1]")): raise ValueError("Remote profiles require HTTPS outside loopback.")
    data=_load(path); data["profiles"][str(name)]={"url":str(url).rstrip("/"),"token_env":token_env,"verify_tls":bool(verify_tls)}; _save(data,path); return data["profiles"][str(name)]
def list_profiles(path=None): return OrderedDict(sorted(_load(path)["profiles"].items()))
def get_profile(name,path=None):
    row=_load(path)["profiles"].get(str(name))
    if not row: raise KeyError("Unknown remote profile: %s"%name)
    return dict(row)
def delete_profile(name,path=None):
    data=_load(path); removed=data["profiles"].pop(str(name),None); _save(data,path); return removed is not None

def request(profile, method, route, payload=None, revision=None, params=None, timeout=20):
    url=profile["url"].rstrip("/")+"/"+route.lstrip("/")
    if params: url += "?"+urlencode(params)
    headers={"Accept":"application/json","X-Lifetxt-Client-Time":__import__('lifetxt.timezone_policy',fromlist=['utcnow']).utcnow().isoformat()}
    token=os.environ.get(str(profile.get("token_env"))) if profile.get("token_env") else None
    if token: headers["Authorization"]="Bearer "+token
    if revision: headers["If-Match"]='"'+str(revision).strip('"')+'"'
    body=None
    if payload is not None: body=json.dumps(payload).encode("utf-8"); headers["Content-Type"]="application/json"
    try:
        with urlopen(Request(url,data=body,headers=headers,method=method),timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8")), dict(response.headers)
    except HTTPError as exc:
        raw=exc.read().decode("utf-8","replace")
        try: detail=json.loads(raw)
        except ValueError: detail={"error":"HTTP_%s"%exc.code,"message":raw}
        raise RuntimeError(json.dumps(detail,ensure_ascii=False))
    except URLError as exc: raise RuntimeError("Remote connection failed: %s"%exc)

def snapshot(profile): return request(profile,"GET","/api/remote/v1/snapshot")[0]
def test_connection(profile):
    cap,_=request(profile,"GET","/api/remote/v1/capabilities"); session,_=request(profile,"GET","/api/remote/v1/session")
    return {"ok":True,"capabilities":cap,"session":session}
def export_snapshot(profile,path):
    value=snapshot(profile)
    from .atomic import atomic_write_text
    atomic_write_text(path,json.dumps(value,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    return path

def render_tui(value):
    lines=["lifetxt remote (read-only)","revision: %s"%value.get("revision","-")]
    for row in value.get("tickets",[]): lines.append("[ticket] %-16s %s"%(row.get("id","-"),row.get("title") or row.get("text") or ""))
    for row in value.get("projects",[]): lines.append("[project] %-15s %s"%(row.get("id") or row.get("name") or "-",row.get("title") or ""))
    return "\n".join(lines)+"\n"

def install_remote_client_cli():
    from . import cli
    if getattr(cli,"_lifetxt_remote_client_v19",False): return
    original=cli.build_parser
    def build_parser():
        parser=original(); subs=next(a for a in parser._actions if isinstance(a,argparse._SubParsersAction))
        if "remote" in subs.choices: return parser
        remote=subs.add_parser("remote",help="Use authenticated Remote Safe Mode."); rs=remote.add_subparsers(dest="remote_command",required=True)
        p=rs.add_parser("profile-set"); p.add_argument("name"); p.add_argument("url"); p.add_argument("--token-env"); p.add_argument("--profiles-file"); p.set_defaults(func=_cmd_set)
        p=rs.add_parser("profile-list"); p.add_argument("--profiles-file"); p.set_defaults(func=_cmd_list)
        p=rs.add_parser("profile-show"); p.add_argument("name"); p.add_argument("--profiles-file"); p.set_defaults(func=_cmd_show)
        p=rs.add_parser("profile-delete"); p.add_argument("name"); p.add_argument("--profiles-file"); p.set_defaults(func=_cmd_delete)
        for name,fn in (("test",_cmd_test),("snapshot",_cmd_snapshot),("tui",_cmd_tui)):
            p=rs.add_parser(name); p.add_argument("profile"); p.add_argument("--profiles-file"); p.set_defaults(func=fn)
        p=rs.add_parser("export"); p.add_argument("profile"); p.add_argument("path"); p.add_argument("--profiles-file"); p.set_defaults(func=_cmd_export)
        return parser
    cli.build_parser=build_parser; cli._lifetxt_remote_client_v19=True

def _emit(v): print(json.dumps(v,ensure_ascii=False,indent=2,sort_keys=True)); return 0
def _cmd_set(a): return _emit(set_profile(a.name,a.url,a.token_env,path=a.profiles_file))
def _cmd_list(a): return _emit(list_profiles(a.profiles_file))
def _cmd_show(a): return _emit(get_profile(a.name,a.profiles_file))
def _cmd_delete(a): return _emit({"deleted":delete_profile(a.name,a.profiles_file)})
def _p(a): return get_profile(a.profile,a.profiles_file)
def _cmd_test(a): return _emit(test_connection(_p(a)))
def _cmd_snapshot(a): return _emit(snapshot(_p(a)))
def _cmd_export(a): return _emit({"path":export_snapshot(_p(a),a.path)})
def _cmd_tui(a): sys.stdout.write(render_tui(snapshot(_p(a)))); return 0
