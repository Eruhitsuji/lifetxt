"""Optional read-only Language Server Protocol 3.17 subset over stdio.

Run explicitly: ``python -m lifetxt.lsp --stdio``. No disk access, subprocess,
network, Core configuration loading or writes happen in this server.
"""

import argparse
import json
import re
import sys

from .lsp_document import Document, MAX_DOCUMENT_BYTES, MAX_DOCUMENTS
from .lsp_features import completion, hover
from .lsp_workspace import workspace_items, workspace_diagnostics

MAX_MESSAGE_BYTES = 2 * 1024 * 1024


class ProtocolError(ValueError):
    pass


def read_message(stream):
    length = None
    total = 0
    while True:
        line = stream.readline(8193)
        if not line and total == 0:
            return None
        total += len(line)
        if not line or total > 8192:
            raise ProtocolError("Invalid or oversized headers")
        if line == b"\r\n":
            break
        try:
            key, value = line.decode("ascii").strip().split(":", 1)
        except (UnicodeError, ValueError) as exc:
            raise ProtocolError("Malformed header") from exc
        if key.lower() == "content-length":
            if (
                length is not None
                or len(value.strip()) > 7
                or not value.strip().isdigit()
            ):
                raise ProtocolError("Invalid Content-Length")
            length = int(value)
    if length is None or not 0 < length <= MAX_MESSAGE_BYTES:
        raise ProtocolError("Invalid or oversized message")
    body = stream.read(length)
    if len(body) != length:
        raise ProtocolError("Truncated message")
    try:
        message = json.loads(body.decode("utf-8"))
    except (UnicodeError, ValueError) as exc:
        raise ProtocolError("Invalid JSON message") from exc
    if not isinstance(message, dict):
        raise ProtocolError("JSON-RPC object required")
    return message


def write_message(stream, message):
    body = json.dumps(message, ensure_ascii=True, separators=(",", ":")).encode("utf-8")
    stream.write(f"Content-Length: {len(body)}\r\n\r\n".encode("ascii") + body)
    stream.flush()


class Server:
    def __init__(self, send, id_key="id"):
        self.send = send
        self.id_key = id_key
        self.documents = {}
        self.initialized = False
        self.shutdown = False
        self.exited = False

    def response(self, id_, result=None, error=None):
        self.send(
            {
                "jsonrpc": "2.0",
                "id": id_,
                **({"error": error} if error else {"result": result}),
            }
        )

    def notify(self, method, params):
        self.send({"jsonrpc": "2.0", "method": method, "params": params})

    def publish(self, document, extra=()):
        self.notify(
            "textDocument/publishDiagnostics",
            {
                "uri": document.uri,
                "version": document.version,
                "diagnostics": document.diagnostics(extra),
            },
        )

    def publish_all(self):
        extra = workspace_diagnostics(self.documents, self.id_key)
        for document in self.documents.values():
            self.publish(document, extra.get(document.uri, ()))

    def handle(self, message):
        request = "id" in message
        id_ = message.get("id")
        method = message.get("method")
        if message.get("jsonrpc") != "2.0" or not isinstance(method, str):
            if request:
                self.response(id_, error={"code": -32600, "message": "Invalid request"})
            return
        if method == "exit":
            self.exited = True
            return
        if self.shutdown:
            if request:
                self.response(
                    id_, error={"code": -32600, "message": "Server is shut down"}
                )
            return
        try:
            params = message.get("params", {})
            if not isinstance(params, dict):
                raise ValueError("Object params required")
            if method == "initialize":
                if self.initialized or not request:
                    raise ValueError("Already initialized or missing request ID")
                self.initialized = True
                result = {
                    "capabilities": {
                        "positionEncoding": "utf-16",
                        "textDocumentSync": {"openClose": True, "change": 1},
                        "completionProvider": {"triggerCharacters": ["[", " ", ":"]},
                        "hoverProvider": True,
                    },
                    "serverInfo": {"name": "lifetxt"},
                }
            elif not self.initialized:
                if request:
                    self.response(
                        id_, error={"code": -32002, "message": "Server not initialized"}
                    )
                return
            elif method == "shutdown":
                if not request:
                    return
                self.shutdown = True
                result = None
            elif method in ("initialized", "$/cancelRequest", "$/setTrace"):
                return
            elif method == "textDocument/didOpen":
                data = params["textDocument"]
                uri = data["uri"]
                self.check_uri(uri)
                if uri in self.documents:
                    raise ValueError("Document already open")
                if len(self.documents) >= MAX_DOCUMENTS:
                    raise ValueError("Maximum 32 open documents")
                doc = Document(
                    uri, data["version"], data["text"], self.id_key, check_links=False
                )
                self.documents[uri] = doc
                self.publish_all()
                return
            elif method == "textDocument/didChange":
                data = params["textDocument"]
                doc = self.documents[data["uri"]]
                version = data["version"]
                if type(version) is not int:
                    raise ValueError("Integer version required")
                if version <= doc.version:
                    return
                changes = params["contentChanges"]
                if not isinstance(changes, list) or not changes:
                    raise ValueError("Full text changes required")
                if any("range" in change for change in changes):
                    raise ValueError("Only full document synchronization supported")
                updated = Document(
                    doc.uri,
                    version,
                    changes[-1]["text"],
                    self.id_key,
                    check_links=False,
                )
                self.documents[doc.uri] = updated
                self.publish_all()
                return
            elif method == "textDocument/didClose":
                uri = params["textDocument"]["uri"]
                self.documents.pop(uri, None)
                self.publish_all()
                self.notify(
                    "textDocument/publishDiagnostics", {"uri": uri, "diagnostics": []}
                )
                return
            elif method in ("textDocument/completion", "textDocument/hover"):
                doc = self.documents[params["textDocument"]["uri"]]
                result = (
                    completion(
                        doc, params["position"], items=workspace_items(self.documents)
                    )
                    if method.endswith("completion")
                    else hover(doc, params["position"])
                )
            else:
                if request:
                    self.response(
                        id_, error={"code": -32601, "message": "Method not found"}
                    )
                return
            if request:
                self.response(id_, result)
        except (
            KeyError,
            TypeError,
            ValueError,
            IndexError,
            OverflowError,
            RecursionError,
        ):
            # Do not echo document text, URI, raw payload or filesystem paths.
            if request:
                self.response(
                    id_,
                    error={
                        "code": -32602,
                        "message": "Invalid params or document limit exceeded",
                    },
                )
            else:
                self.notify(
                    "window/logMessage",
                    {
                        "type": 2,
                        "message": "lifetxt rejected an invalid, stale, or oversized document notification; reopen the document to resynchronize.",
                    },
                )

    @staticmethod
    def check_uri(uri):
        # Opaque identifiers, never converted to local paths, including Remote.
        if not isinstance(uri, str) or not uri or len(uri) > 4096:
            raise ValueError("Invalid document URI")


def serve(input_stream, output_stream, id_key="id"):
    server = Server(lambda msg: write_message(output_stream, msg), id_key)
    while not server.exited:
        try:
            message = read_message(input_stream)
        except (ProtocolError, RecursionError):
            write_message(
                output_stream,
                {
                    "jsonrpc": "2.0",
                    "id": None,
                    "error": {
                        "code": -32700,
                        "message": "Invalid or oversized LSP frame",
                    },
                },
            )
            return 1
        if message is None:
            return 0 if server.shutdown else 1
        server.handle(message)
    return 0 if server.shutdown else 1


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--stdio", required=True, action="store_true", help="Use LSP stdio transport"
    )
    parser.add_argument(
        "--id-key",
        default="id",
        help="Explicit ID detail key (Core configuration is not loaded)",
    )
    args = parser.parse_args(argv)
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_-]*", args.id_key):
        parser.error("--id-key must be a nonempty detail key")
    return serve(sys.stdin.buffer, sys.stdout.buffer, args.id_key)


if __name__ == "__main__":
    raise SystemExit(main())
