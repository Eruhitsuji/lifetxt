"""Assemble the packaged Web UI from split HTML/CSS/JavaScript resources.

``HTML_PAGE`` remains the pristine page. ``surface_runtime`` may rebind
``webapp.HTML_PAGE`` with compatibility scripts without mutating this value.
"""

import base64
from importlib import resources


def _read_resource(name: str) -> str:
    return resources.files(__package__).joinpath(name).read_text(encoding="utf-8")


_STYLE_MARKER = "__LIFETXT_WEB_STYLES__"
_SCRIPT_MARKER = "__LIFETXT_WEB_SCRIPT__"
WEB_SESSION_UI = r"""<script>
(()=>{const labels=(navigator.language||'en').toLowerCase().startsWith('ja')
?{principal:'利用者',workspace:'ワークスペース',role:'権限',owner:'Owner',editor:'Editor',viewer:'Viewer',readOnly:'閲覧のみ',logout:'サインアウト',login:'再ログイン',expired:'セッションを確認できません。再ログインしてください。'}
:{principal:'Signed in',workspace:'Workspace',role:'Role',owner:'Owner',editor:'Editor',viewer:'Viewer',readOnly:'Read-only',logout:'Sign out',login:'Sign in again',expired:'Session unavailable. Sign in again.'};
const nativeFetch=window.fetch.bind(window);let sessionData=null;let sessionReady;
window.fetch=function(input,init={}){const method=String(init.method||(input instanceof Request?input.method:'GET')).toUpperCase();const raw=input instanceof URL?input.href:(typeof input==='string'?input:input.url);const url=new URL(raw,location.href);
if(url.origin===location.origin&&!['GET','HEAD','OPTIONS'].includes(method)&&!['/api/web/v1/browser/login','/api/web/v1/browser/session'].includes(url.pathname))return Promise.resolve(sessionReady).then(()=>{
if(!sessionData)return nativeFetch(input,init);const headers=new Headers(init.headers||(input instanceof Request?input.headers:undefined));headers.set(sessionData.csrf_header||'X-CSRF-Token',sessionData.csrf_token||'');return nativeFetch(input,{...init,headers,credentials:init.credentials||'same-origin'});});return nativeFetch(input,init);};
sessionReady=nativeFetch('/api/web/v1/browser/session',{credentials:'same-origin',cache:'no-store'}).then(async response=>{
if(response.status===404)return null;if(response.status===401)throw new Error('session');if(!response.ok)return null;sessionData=await response.json();return sessionData;});
sessionReady.then(data=>{if(!data)return;
const bar=document.createElement('aside');bar.setAttribute('aria-label','Workspace access');
bar.style.cssText='display:flex;gap:.75rem;align-items:center;justify-content:space-between;flex-wrap:wrap;padding:.55rem 1rem;background:#edf6f5;color:#27343d;font:14px system-ui,sans-serif;border-bottom:1px solid #c8d7d9';
const summary=document.createElement('span');const principal=(data.principal||{}).display_name||(data.principal||{}).id||'—';
const role=labels[data.role]||data.role||'—';const parts=[labels.principal+': '+principal,labels.workspace+': '+(data.workspace||'—'),labels.role+': '+role];if(data.read_only)parts.push(labels.readOnly);summary.textContent=parts.join(' · ');bar.appendChild(summary);
const button=document.createElement('button');button.type='button';button.textContent=labels.logout;button.style.cssText='min-height:36px;padding:.35rem .75rem';
button.addEventListener('click',async()=>{button.disabled=true;try{await fetch('/api/web/v1/browser/logout',{method:'POST',credentials:'same-origin'});}finally{location.assign('/web-login');}});bar.appendChild(button);document.body.prepend(bar);
}).catch(problem=>{if(problem.message!=='session'||location.pathname==='/web-login')return;const note=document.createElement('aside');note.textContent=labels.expired+' ';const link=document.createElement('a');link.href='/web-login';link.textContent=labels.login;note.appendChild(link);note.style.cssText='padding:.5rem 1rem;background:#fff0e8;color:#632f00';document.body.prepend(note);});})();
</script>"""
_BRAND_FAVICON_SVG = _read_resource("web_icon.svg")
_BRAND_MARK_SVG = """<svg viewBox="0 0 512 512" width="27" height="27" focusable="false" aria-hidden="true" data-lifetxt-geometry="v3">
  <defs>
    <mask id="web-notebook-sprout-separator" maskUnits="userSpaceOnUse" x="0" y="0" width="512" height="512">
      <rect width="512" height="512" fill="white"/>
      <path d="M302 420C305 380 315 348 338 323C343 318 352 322 348 329C328 352 320 383 319 420Z" fill="black" stroke="black" stroke-width="12" stroke-linejoin="round"/>
      <path d="M335 348C306 352 284 334 281 305C310 303 333 320 339 342C340 346 339 347 335 348Z" fill="black" stroke="black" stroke-width="12" stroke-linejoin="round"/>
      <path d="M338 346C343 321 364 304 394 304C392 330 375 345 344 350C340 350 337 349 338 346Z" fill="black" stroke="black" stroke-width="12" stroke-linejoin="round"/>
    </mask>
  </defs>
  <g data-lifetxt-base="v3" shape-rendering="geometricPrecision">
    <path data-lifetxt-part="notebook" d="M150 84H291L339 132V364C339 384 327 396 307 396H150C130 396 118 384 118 364V116C118 96 130 84 150 84Z" fill="#FFFFFF" mask="url(#web-notebook-sprout-separator)"/>
    <path data-lifetxt-part="fold" d="M291 84V116C291 126 297 132 307 132H339Z" fill="#C8D7D9"/>
    <circle data-lifetxt-part="row-1-dot" cx="162" cy="184" r="8" fill="#27343D"/>
    <rect data-lifetxt-part="row-1-line" x="190" y="176" width="94" height="16" rx="8" fill="#27343D"/>
    <circle data-lifetxt-part="row-2-dot" cx="162" cy="242" r="8" fill="#27343D"/>
    <rect data-lifetxt-part="row-2-line" x="190" y="234" width="80" height="16" rx="8" fill="#27343D"/>
    <circle data-lifetxt-part="row-3-dot" cx="162" cy="300" r="8" fill="#27343D"/>
    <rect data-lifetxt-part="row-3-line" x="190" y="292" width="66" height="16" rx="8" fill="#27343D"/>
    <path data-lifetxt-part="stem" d="M302 420C305 380 315 348 338 323C343 318 352 322 348 329C328 352 320 383 319 420Z" fill="#BFF3E6"/>
    <path data-lifetxt-part="leaf-left" d="M335 348C306 352 284 334 281 305C310 303 333 320 339 342C340 346 339 347 335 348Z" fill="#BFF3E6"/>
    <path data-lifetxt-part="leaf-right" d="M338 346C343 321 364 304 394 304C392 330 375 345 344 350C340 350 337 349 338 346Z" fill="#BFF3E6"/>
  </g>
</svg>"""
_CSS_RESOURCE_NAMES = (
    "web_assets_css_01.css",
    "web_assets_css_02.css",
    "web_assets_css_03.css",
    "web_assets_css_04.css",
    "web_assets_css_06.css",
    "web_assets_css_07.css",
    "web_assets_css_05.css",
)
_JS_RESOURCE_NAMES = (
    "web_assets_js_01.js",
    "web_assets_js_02.js",
    "web_assets_js_03.js",
    "web_assets_js_04.js",
    "web_assets_js_05.js",
    "web_assets_js_06.js",
    "web_assets_js_07.js",
    "web_assets_js_08.js",
    "web_assets_js_09.js",
    "web_assets_js_10.js",
    "web_assets_js_11.js",
    "web_assets_js_12.js",
    "web_assets_js_13.js",
    "web_assets_js_14.js",
    "web_assets_js_15.js",
    "web_assets_js_16.js",
    "web_assets_js_17.js",
    "web_assets_js_18.js",
    "web_assets_js_19.js",
    "web_assets_js_20.js",
    "web_assets_js_21.js",
    "web_assets_js_22.js",
    "web_assets_js_23.js",
    "web_assets_js_24.js",
)


def web_resource_bytes(name: str) -> bytes:
    """Read one allowlisted installability resource from the package."""
    allowed = {
        "web_app_manifest.json",
        "planner_app_manifest.json",
        "state_app_manifest.json",
        "desk_app_manifest.json",
        "web_icon_180.png",
        "web_icon_192.png",
        "web_icon_512.png",
    }
    if name not in allowed:
        raise ValueError("Unknown Web installability resource: %s" % name)
    return resources.files(__package__).joinpath(name).read_bytes()


def _assemble_planner_html() -> str:
    template = _read_resource("web_planner.html")
    template = template.replace(
        "__PLANNER_CSS__", _read_resource("web_tokens.css")
        + _read_resource("web_tokens_auto.css")
        + _read_resource("web_planner.css")
    )
    script = _read_resource("web_layout_url.js") + _read_resource("web_planner.js")
    return template.replace(
        "<script>__PLANNER_JS__</script>",
        "<script>" + script + "</script>",
    )


PLANNER_HTML_PAGE = _assemble_planner_html()


def _assemble_desk_html() -> str:
    template = _read_resource("web_desk.html")
    template = template.replace(
        "__DESK_CSS__", _read_resource("web_tokens.css")
        + _read_resource("web_tokens_auto.css")
        + _read_resource("web_presence.css")
        + _read_resource("web_desk.css")
    )
    script = (
        _read_resource("web_layout_url.js")
        + _read_resource("web_presence.js")
        + _read_resource("web_desk_clock.js")
        + _read_resource("web_desk.js")
    )
    return template.replace(
        "<script>__DESK_JS__</script>",
        "<script>" + script + "</script>",
    )


DESK_HTML_PAGE = _assemble_desk_html()


def _assemble_state_html() -> str:
    template = _read_resource("web_state.html")
    if template.count("__STATE_CSS__") != 1 or template.count("__STATE_JS__") != 1:
        raise RuntimeError("web_state.html must contain one CSS and JS marker")
    template = template.replace(
        "__STATE_CSS__", _read_resource("web_tokens.css")
        + _read_resource("web_tokens_auto.css")
        + _read_resource("web_presence.css")
        + _read_resource("web_state.css")
    )
    script = _read_resource("web_presence.js") + _read_resource("web_state.js")
    return template.replace(
        "<script>__STATE_JS__</script>",
        "<script>" + script + "</script>",
    )


STATE_HTML_PAGE = _assemble_state_html()


def _svg_data_uri(svg: str) -> str:
    payload = base64.b64encode(svg.encode("utf-8")).decode("ascii")
    return f"data:image/svg+xml;base64,{payload}"


def _apply_brand_assets(template: str) -> str:
    favicon = _svg_data_uri(_BRAND_FAVICON_SVG)
    title = "<title>life.txt</title>"
    brand_mark = '<span class="brand-mark" aria-hidden="true">✓</span>'
    if template.count(title) != 1 or template.count(brand_mark) != 1:
        raise RuntimeError("web_assets.html brand anchors must each occur exactly once")
    template = template.replace(
        title,
        title
        + '\n  <link data-lifetxt-brand="favicon" rel="icon" '
        + f'type="image/svg+xml" href="{favicon}">',
    )
    return template.replace(
        brand_mark,
        '<span class="brand-mark" data-lifetxt-brand="mark" aria-hidden="true">'
        + _BRAND_MARK_SVG
        + "</span>",
    ).rstrip("\r\n")


def _assemble_html() -> str:
    template = _read_resource("web_assets.html")
    if template.count(_STYLE_MARKER) != 1 or template.count(_SCRIPT_MARKER) != 1:
        raise RuntimeError("web_assets.html must contain exactly one CSS and JS marker")
    template = _apply_brand_assets(template)
    styles = _read_resource("web_tokens.css") + "".join(
        _read_resource(name) for name in _CSS_RESOURCE_NAMES
    )
    script = "".join(_read_resource(name) for name in _JS_RESOURCE_NAMES)
    template = template.replace(_STYLE_MARKER, styles)
    return template.replace(
        "<script>\n" + _SCRIPT_MARKER + "  </script>",
        "<script>\n" + script + "  </script>",
    )


HTML_PAGE = _assemble_html()
