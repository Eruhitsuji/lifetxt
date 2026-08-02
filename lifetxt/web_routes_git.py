"""`/api/git/*` routes, registered onto the app built by :mod:`lifetxt.webapp`.

Moved out of ``create_app`` by #84 as the first route group, establishing the
registration hook the remaining groups reuse.

``fastapi`` is imported inside :func:`register_git_routes`, never at module
level. ``webapp.create_app`` imports it the same way behind an ``ImportError``
guard, which is what lets ``import lifetxt.webapp`` work without the Web extras
and what keeps the no-Web CI job green. A module-level import here would undo
that.
"""

from __future__ import unicode_literals

import os


def register_git_routes(app):
    """Attach the Git API routes to ``app``.

    Called from ``create_app`` after fastapi has imported successfully, so the
    local import below cannot fail in a way the caller has not already handled.
    The routes close over ``app`` for ``app.state.config`` and
    ``app.state.writable_path``, exactly as they did inline.
    """
    from fastapi import Body, HTTPException, Request

    def _git_guard(request):
        git_config = (app.state.config or {}).get("git", {})
        if not git_config.get("enable_api"):
            raise HTTPException(
                status_code=403,
                detail={
                    "error": "FORBIDDEN",
                    "message": "Git API is not enabled. Set git.enable_api: true in config.",
                    "detail": None,
                },
            )
        host = request.client.host if request.client else None
        if host not in ("127.0.0.1", "::1", "localhost"):
            raise HTTPException(
                status_code=403,
                detail={
                    "error": "FORBIDDEN",
                    "message": "Git API is restricted to loopback access.",
                    "detail": None,
                },
            )

    def _run_git(cmd, cwd=None):
        import subprocess

        result = subprocess.run(
            cmd,
            cwd=cwd or os.path.dirname(os.path.abspath(app.state.writable_path)),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True,
        )
        return {
            "stdout": result.stdout,
            "stderr": result.stderr,
            "exit_code": result.returncode,
            "ok": result.returncode == 0,
        }

    @app.get("/api/git/status")
    def git_status(request: Request):
        _git_guard(request)
        return _run_git(["git", "status", "--short"])

    @app.post("/api/git/pull")
    def git_pull(request: Request):
        _git_guard(request)
        return _run_git(["git", "pull"])

    @app.post("/api/git/commit")
    def git_commit(request: Request, payload=Body(...)):
        _git_guard(request)
        message = payload.get("message", "") if isinstance(payload, dict) else ""
        if not message:
            raise HTTPException(
                status_code=400,
                detail={
                    "error": "ERROR",
                    "message": "commit message is required.",
                    "detail": None,
                },
            )
        writable = app.state.writable_path
        import subprocess

        cwd = os.path.dirname(os.path.abspath(writable))
        add_result = subprocess.run(
            ["git", "add", os.path.abspath(writable)],
            cwd=cwd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True,
        )
        if add_result.returncode != 0:
            return {
                "stdout": add_result.stdout,
                "stderr": add_result.stderr,
                "exit_code": add_result.returncode,
                "ok": False,
            }
        return _run_git(["git", "commit", "-m", message], cwd=cwd)

    @app.post("/api/git/push")
    def git_push(request: Request):
        _git_guard(request)
        return _run_git(["git", "push"])

    @app.get("/api/git/log")
    def git_log(request: Request, n: int = 5, count: bool = False):
        _git_guard(request)
        n = min(max(1, n), 50)
        result = _run_git(["git", "log", "--pretty=format:%H\t%s\t%ai", "-%d" % n])
        commits = []
        if result.get("ok") and result.get("stdout"):
            for line in result["stdout"].strip().splitlines():
                parts = line.split("\t", 2)
                if len(parts) >= 2:
                    commits.append(
                        {
                            "hash": parts[0][:8],
                            "message": parts[1],
                            "date": parts[2] if len(parts) > 2 else "",
                        }
                    )
        total = None
        if count:
            count_result = _run_git(["git", "rev-list", "--count", "HEAD"])
            if count_result.get("ok") and count_result.get("stdout"):
                try:
                    total = int(count_result["stdout"].strip())
                except ValueError:
                    pass
        return {"commits": commits, "ok": result.get("ok", False), "total": total}
