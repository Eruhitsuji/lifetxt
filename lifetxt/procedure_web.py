"""GET-only procedure projection over the existing server read allowlist."""

import hashlib
import json
import os
from importlib import resources
from urllib.parse import quote

from .ids import id_key_from_config
from .procedure_cli import read_definition, read_procedure_source
from .procedure_definition import ProcedureError, project_definition
from .procedure_graph import MAX_OUTPUT_BYTES, render_procedure
from .procedure_validation import validate_definition

MAX_SOURCES = 64
MAX_ROOTS = 100
MAX_CATALOG_BYTES = 1024 * 1024


def _token(path):
    canonical = os.path.normcase(os.path.realpath(os.path.abspath(path)))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def sources(app):
    from .webapp import normalize_server_paths

    paths = normalize_server_paths(app.state.paths)
    if len(paths) > MAX_SOURCES:
        raise ValueError("Procedure source limit exceeded.")
    return {_token(path): path for path in paths if path != "-"}


def _diagnostics(rows):
    # Definition errors may mention IDs, but never include private source paths.
    return [
        {"code": d.code, "message": d.message, "line": d.line, "severity": d.severity}
        for d in rows
    ]


def _bounded(value, limit=None):
    limit = MAX_OUTPUT_BYTES if limit is None else limit
    if len(json.dumps(value, ensure_ascii=False).encode("utf-8")) > limit:
        raise ValueError("Procedure response limit exceeded.")
    return value


def _href(source, root):
    return "/procedures?source=%s&id=%s" % (source, quote(root, safe=""))


def catalog(app):
    rows, failures = [], []
    for token, path in sources(app).items():
        try:
            items, revision = read_procedure_source(path)
            roots = [
                item for item in items if item.details.get("proc_role") == ["root"]
            ]
            if len(rows) + len(roots) > MAX_ROOTS:
                raise ValueError("Procedure root limit exceeded.")
            for root in roots:
                ids = root.details.get("id", [])
                ident = ids[0] if len(ids) == 1 else ""
                diagnostics = []
                try:
                    graph = validate_definition(
                        project_definition(
                            items,
                            ident,
                            template_revision=revision,
                            id_key=id_key_from_config(app.state.config),
                        )
                    )
                    diagnostics = _diagnostics(graph.diagnostics)
                    valid = True
                except ProcedureError as exc:
                    diagnostics = _diagnostics(exc.diagnostics)
                    valid = False
                rows.append(
                    {
                        "source": token,
                        "id": ident,
                        "title": root.title,
                        "valid": valid,
                        "diagnostics": diagnostics,
                        "href": _href(token, ident),
                    }
                )
        except (OSError, ProcedureError):
            failures.append({"source": token, "error": "PROCEDURE_SOURCE_UNAVAILABLE"})
    return _bounded(
        {"schema": "procedure-catalog-v1", "procedures": rows, "failures": failures},
        MAX_CATALOG_BYTES,
    )


def projection(graph, source):
    definition = graph.projection
    kinds = dict(graph.step_kinds)

    def node(value):
        return {
            "id": value.id,
            "title": value.title,
            "status": value.status,
            "body": list(value.body),
            "parent": value.parent,
            "depth": value.depth,
            "line": value.line,
            "kind": kinds.get(value.id, "root"),
            "item_href": "/?id=" + quote(value.id, safe=""),
        }

    return _bounded(
        {
            "schema": "procedure-v1",
            "mode": "definition",
            "source": source,
            "template_revision": definition.template_revision,
            "root": node(definition.root),
            "steps": [node(step) for step in definition.steps],
            "start": graph.start,
            "cyclic": graph.cyclic,
            "edges": [
                {"source": e.source, "target": e.target, "label": e.label}
                for e in graph.edges
            ],
            "diagnostics": _diagnostics(graph.diagnostics),
            "formats": {
                format: render_procedure(graph, format)
                for format in ("text", "mermaid", "dot")
            },
        }
    )


def register_procedure_routes(app):
    from fastapi import HTTPException, Response
    from fastapi.responses import HTMLResponse

    def headers(response):
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"

    @app.get("/procedures", response_class=HTMLResponse)
    def page():
        package = resources.files("lifetxt")
        text = package.joinpath("procedure_web.html").read_text(encoding="utf-8")
        for kind in ("css", "js"):
            text = text.replace(
                "__PROCEDURE_%s__" % kind.upper(),
                package.joinpath("procedure_web." + kind).read_text(encoding="utf-8"),
            )
        return HTMLResponse(
            text,
            headers={
                "Cache-Control": "no-store",
                "X-Frame-Options": "DENY",
                "Referrer-Policy": "no-referrer",
                "Content-Security-Policy": "default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; connect-src 'self'; base-uri 'none'; frame-ancestors 'none'; form-action 'none'",
            },
        )

    @app.get("/api/procedures")
    def get_catalog(response: Response):
        headers(response)
        try:
            return catalog(app)
        except ValueError:
            raise HTTPException(
                422,
                {
                    "error": "PROCEDURE_LIMIT",
                    "message": "Reduce the configured procedure sources or definitions.",
                },
            )

    @app.get("/api/procedures/{source}/{root_id}")
    def get_definition(source: str, root_id: str, response: Response):
        headers(response)
        try:
            path = sources(app).get(source)
            if path is None:
                raise HTTPException(
                    404,
                    {
                        "error": "PROCEDURE_NOT_FOUND",
                        "message": "Unknown procedure source.",
                    },
                )
            return projection(
                read_definition(
                    path, root_id, id_key=id_key_from_config(app.state.config)
                ),
                source,
            )
        except ProcedureError as exc:
            raise HTTPException(
                422,
                {
                    "error": "INVALID_PROCEDURE",
                    "message": "Definition could not be validated.",
                    "diagnostics": _diagnostics(exc.diagnostics),
                },
            )
        except OSError:
            raise HTTPException(
                404,
                {
                    "error": "PROCEDURE_SOURCE_UNAVAILABLE",
                    "message": "Configured source is unavailable.",
                },
            )
        except ValueError:
            raise HTTPException(
                422,
                {
                    "error": "PROCEDURE_LIMIT",
                    "message": "Procedure exceeds the read limits.",
                },
            )
