"""Remote Safe Mode schemas."""
from __future__ import unicode_literals
from collections import OrderedDict
BASE="https://github.com/Eruhitsuji/lifetxt/raw/main/dist/schemas/"; DRAFT="https://json-schema.org/draft/2020-12/schema"
def _s(name,title,props,req=()): return {"$schema":DRAFT,"$id":BASE+name,"title":title,"type":"object","properties":props,"required":list(req),"additionalProperties":True}
def schema_bundle_v19():
    return OrderedDict((
      ("remote-principal-v1.schema.json",_s("remote-principal-v1.schema.json","Remote principal",{"id":{"type":"string"},"role":{"enum":["owner","editor","reader","auditor"]},"scopes":{"type":"array","items":{"type":"string"}},"projects":{"type":"array","items":{"type":"string"}},"groups":{"type":"array","items":{"type":"string"}},"visibilities":{"type":"array","items":{"type":"string"}},"disabled":{"type":"boolean"}},("id","role","scopes"))),
      ("remote-access-policy-v1.schema.json",_s("remote-access-policy-v1.schema.json","Remote access policy",{"schema":{"const":"remote-access-policy-v1.schema.json"},"contract_version":{"const":"1"},"enabled":{"type":"boolean"},"browser_ui":{"type":"boolean"},"authentication":{"type":"array","items":{"type":"string"}},"roles":{"type":"object"},"exact_revision_required":{"type":"boolean"},"https_required":{"type":"boolean"},"write_operations":{"type":"array","items":{"type":"string"}},"read_operations":{"type":"array","items":{"type":"string"}}},("schema","contract_version","enabled","exact_revision_required"))),
      ("remote-session-v1.schema.json",_s("remote-session-v1.schema.json","Remote session",{"schema":{"const":"remote-session-v1.schema.json"},"principal":{"$ref":BASE+"remote-principal-v1.schema.json"},"authentication":{"type":"string"},"request_id":{"type":"string"}},("schema","principal","authentication","request_id"))),
      ("remote-snapshot-v1.schema.json",_s("remote-snapshot-v1.schema.json","Remote snapshot",{"schema":{"const":"remote-snapshot-v1.schema.json"},"revision":{"type":"string"},"tickets":{"type":"array","items":{"type":"object"}},"projects":{"type":"array","items":{"type":"object"}},"read_only":{"type":"boolean"}},("schema","revision","tickets","projects"))),
      ("remote-audit-event-v1.schema.json",_s("remote-audit-event-v1.schema.json","Remote audit event",{"schema":{"const":"remote-audit-event-v1.schema.json"},"version":{"const":"1"},"at":{"type":"string","format":"date-time"},"request_id":{"type":"string"},"principal":{"type":["string","null"]},"role":{"type":["string","null"]},"action":{"type":"string"},"outcome":{},"client":{"type":"string"},"detail":{"type":"object"}},("schema","version","at","request_id","action","outcome"))),
      ("remote-profile-v2.schema.json",_s("remote-profile-v2.schema.json","Remote profile store",{"version":{"const":2},"profiles":{"type":"object","additionalProperties":{"type":"object","required":["url"],"properties":{"url":{"type":"string"},"token_env":{"type":["string","null"]},"verify_tls":{"type":"boolean"}}}}},("version","profiles"))),
    ))
def schema_samples_v19():
    from .remote_access import capability
    return OrderedDict((
      ("remote-principal-v1.schema.json",{"id":"alice","role":"reader","scopes":["read"],"projects":["web"],"groups":[],"visibilities":["public","shared"],"disabled":False}),
      ("remote-access-policy-v1.schema.json",capability({"remote":{"enabled":True}})),
      ("remote-session-v1.schema.json",{"schema":"remote-session-v1.schema.json","principal":{"id":"alice","role":"reader","scopes":["read"]},"authentication":"bearer","request_id":"req-1"}),
      ("remote-snapshot-v1.schema.json",{"schema":"remote-snapshot-v1.schema.json","revision":"0"*64,"tickets":[],"projects":[],"read_only":True}),
      ("remote-audit-event-v1.schema.json",{"schema":"remote-audit-event-v1.schema.json","version":"1","at":"2026-07-26T00:00:00+00:00","request_id":"req-1","principal":"alice","role":"reader","action":"GET /api/remote/v1/snapshot","outcome":200,"client":"127.0.0.1","detail":{}}),
      ("remote-profile-v2.schema.json",{"version":2,"profiles":{"home":{"url":"https://example.test","token_env":"LIFETXT_TOKEN","verify_tls":True}}}),
    ))
def install_schema_extensions_v19():
    from . import release_policy,safety_foundation
    if getattr(release_policy,"_lifetxt_schema_extensions_v19",False): return
    ob=safety_foundation.schema_bundle; osamp=release_policy._schema_samples
    def bundle(): r=OrderedDict(ob()); r.update(schema_bundle_v19()); return r
    def samples(): r=OrderedDict(osamp()); r.update(schema_samples_v19()); return r
    safety_foundation.schema_bundle=bundle; release_policy.schema_bundle=bundle; release_policy._schema_samples=samples; release_policy._lifetxt_schema_extensions_v19=True
