"""Current-authority resolver: opaque identity possession is never byte authority."""

import hashlib
import json
import os
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path

from . import attachment_snapshot
from .attachments import split_value
from .collaboration import resolve_membership, selected_workspace_name
from .ids import id_key_from_config
from .parser import parse_text
from .remote_access import principal_registry, can_access
from .remote_backend import _access_for_item, _opaque_id
from .resource_reference_policy import policy, fingerprint, safe_text
from .resource_reference_store import BindingUnavailable
from .workspace import resolve_workspace


class ResourceFailure(ValueError):
    def __init__(self, code="RESOURCE_UNAVAILABLE"):
        self.code = code
        super().__init__(code)


@dataclass
class ReadContext:
    principal_id: str
    deadline: float
    cancel: threading.Event = field(default_factory=threading.Event)
    workers: list = field(default_factory=list)

    def remaining(self):
        remaining = self.deadline - time.monotonic()
        if self.cancel.is_set() or remaining <= 0:
            raise ResourceFailure("RESOURCE_BUSY")
        return min(30, remaining)

    def stopped(self):
        return all(event.is_set() for event in self.workers)


class ResourceResolver:
    def __init__(self, store, config_loader, *, reader=None):
        self.store = store
        self.config_loader = config_loader
        self.reader = reader or attachment_snapshot.read_snapshot

    def _read(self, path, cap, context, root=None):
        path = Path(path).absolute()
        root = Path(root).absolute() if root else path.parent
        relative = os.path.relpath(path, root)
        if relative.startswith("../") or relative in ("..", "."):
            raise ResourceFailure()
        completed = threading.Event()
        completed.set()
        context.workers[:] = [event for event in context.workers if not event.is_set()]
        context.workers.append(completed)
        try:
            result = self.reader(
                root,
                relative,
                cap,
                seconds=context.remaining(),
                cancel=context.cancel,
                principal=context.principal_id,
                completed=completed,
            )
            if not result.identity:
                raise ResourceFailure()
            return result
        except (ValueError, OSError):
            raise ResourceFailure() from None

    def _configuration(self, context, byte_action=False):
        context.remaining()
        config = self.config_loader(context)
        rules = policy(config)
        if not rules["enabled"]:
            raise ResourceFailure("UNSUPPORTED_CONTRACT")
        principal = principal_registry(config).get(context.principal_id)
        if (
            not principal
            or principal.get("disabled")
            or principal.get("disclosure_mode") != "restricted-resource"
        ):
            raise ResourceFailure()
        if "read" not in principal["scopes"] or (
            byte_action and "attachment:read" not in principal["scopes"]
        ):
            raise ResourceFailure()
        membership = resolve_membership(config, principal)
        if (
            not membership["collaboration_enabled"]
            or not membership["permissions"]["read"]
        ):
            raise ResourceFailure()
        name = selected_workspace_name(config)
        workspace = _opaque_id("workspace", name)
        if workspace != rules["workspace_id"]:
            raise ResourceFailure()
        return config, rules, principal, workspace

    def _sources(self, config, context):
        resolved = resolve_workspace(config)
        # Only declared concrete files, never unbounded/glob/directory enrollment.
        if len(resolved["sources"]) > 100:
            raise ResourceFailure()
        records, all_items = {}, []
        workspace = _opaque_id("workspace", selected_workspace_name(config))
        idkey = id_key_from_config(config)
        for index, source in enumerate(resolved["sources"]):
            if len(source["files"]) != 1 or source.get("matched_glob"):
                raise ResourceFailure()
            path = source["files"][0]
            snapshot = self._read(path, 1048576, context)
            source_id = _opaque_id("source", workspace, index, 0, source["role"])
            self.store.verify_source(
                workspace, source_id, snapshot.revision, snapshot.continuity
            )
            items, diagnostics = parse_text(snapshot.data.decode("utf-8"), id_key=idkey)
            if len(items) > 5000 or any(row.severity == "error" for row in diagnostics):
                raise ResourceFailure()
            if len(all_items) + len(items) > 10000:
                raise ResourceFailure()
            all_items.extend(items)
            source_id = _opaque_id("source", workspace, index, 0, source["role"])
            records[source_id] = (path, snapshot, items, source)
        return records, all_items

    def _item(self, source_id, item_id, config, principal, context):
        records, all_items = self._sources(config, context)
        if source_id not in records:
            raise ResourceFailure()
        path, snapshot, items, source = records[source_id]
        key = id_key_from_config(config)
        matches = [item for item in all_items if item_id in item.details.get(key, [])]
        if (
            not safe_text(item_id)
            or len(matches) != 1
            or matches[0] not in items
            or matches[0].details.get(key) != [item_id]
        ):
            raise ResourceFailure()
        item = matches[0]
        if not source.get("default_visible", True) or not can_access(
            principal, **_access_for_item(item)
        ):
            raise ResourceFailure()
        return path, snapshot, item

    def _association(self, row, config, context, principal):
        from .attachment_transactions import (
            _attachment_root,
            _attachment_settings,
            _enforce_mime_policy,
        )

        path, source, item = self._item(
            row["source"], row["item"], config, principal, context
        )
        selectors = policy(config)["enrolled_items"]
        if {
            "source_id": row["source"],
            "item_id": row["item"],
            "attachment": row["association"],
        } not in selectors:
            self.store.detach(row["ref"])
            raise ResourceFailure()
        if (
            source.revision != row["source_hash"]
            or json.dumps(source.continuity) != row["source_identity"]
        ):
            self.store.detach(row["ref"])
            raise ResourceFailure()
        if item.details.get("file", []).count(row["association"]) != 1:
            self.store.detach(row["ref"])
            raise ResourceFailure()
        relative, _ = split_value(row["association"])
        if (
            not relative
            or "\\" in relative
            or os.path.isabs(relative)
            or "\x00" in relative
        ):
            raise ResourceFailure()
        target = Path(path).parent / relative
        cap = min(
            policy(config)["limits"]["file_bytes"],
            _attachment_settings(config)["max_file_bytes"],
        )
        _enforce_mime_policy(config, str(target), "application/octet-stream")
        try:
            resource = self._read(target, cap, context, _attachment_root(config, path))
        except ResourceFailure:
            self.store.detach(row["ref"])
            raise
        if json.dumps(resource.identity) != row["resource_identity"]:
            self.store.detach(row["ref"])
            raise ResourceFailure()
        return source, resource

    def enroll_selected(self, context):
        """Explicit owner-config startup enrollment. Never called by discovery."""
        from .attachment_transactions import (
            _attachment_root,
            _attachment_settings,
            _enforce_mime_policy,
        )

        config, rules, principal, workspace = self._configuration(context)
        references = []
        for entry in rules["enrolled_items"]:
            path, source, item = self._item(
                entry["source_id"], entry["item_id"], config, principal, context
            )
            if item.details.get("file", []).count(entry["attachment"]) != 1:
                raise ResourceFailure()
            relative, _ = split_value(entry["attachment"])
            if not relative or os.path.isabs(relative) or "\\" in relative:
                raise ResourceFailure()
            cap = min(
                rules["limits"]["file_bytes"],
                _attachment_settings(config)["max_file_bytes"],
            )
            target = Path(path).parent / relative
            _enforce_mime_policy(config, str(target), "application/octet-stream")
            resource = self._read(target, cap, context, _attachment_root(config, path))
            # Authoritative snapshot recheck before committing the association.
            again = self._read(path, 1048576, context)
            if again != source or fingerprint(
                self.config_loader(context)
            ) != fingerprint(config):
                raise ResourceFailure()
            references.append(
                self.store.enroll(
                    workspace,
                    entry["source_id"],
                    entry["item_id"],
                    entry["attachment"],
                    source.revision,
                    source.continuity,
                    resource.identity,
                    fingerprint(config),
                )
            )
        return references

    def _resolved(self, workspace, reference, context, byte_action):
        config, rules, principal, selected = self._configuration(context, byte_action)
        if workspace != selected:
            raise ResourceFailure()
        row = self.store.get(selected, reference)
        source, resource = self._association(row, config, context, principal)
        current_config, _, _, _ = self._configuration(context, byte_action)
        if fingerprint(current_config) != fingerprint(config):
            raise ResourceFailure()
        again_source, again_resource = self._association(
            row, config, context, principal
        )
        if again_source != source:
            self.store.detach(reference)
            raise ResourceFailure()
        if again_resource != resource:
            raise ResourceFailure("STALE_REVISION")
        current_config, _, _, _ = self._configuration(context, byte_action)
        if fingerprint(current_config) != fingerprint(config):
            raise ResourceFailure()
        tokens = self.store.revisions(
            row, source.revision, resource.revision, fingerprint(config)
        )
        return row, resource, tokens, rules

    def discover(self, workspace, source_id, item_id, context):
        try:
            config, _, principal, selected = self._configuration(context)
            if workspace != selected:
                raise ResourceFailure()
            self._item(source_id, item_id, config, principal, context)
            rows = self.store.item_bindings(workspace, source_id, item_id)
            resources = []
            for row in rows:
                try:
                    _, resource, tokens, rules = self._resolved(
                        workspace, row["ref"], context, False
                    )
                except (BindingUnavailable, ResourceFailure):
                    continue
                descriptor = dict(
                    contract_version="1",
                    resource_ref=row["ref"],
                    kind="file",
                    display_name="Attachment",
                    source_revision=tokens[0],
                    resource_revision=tokens[1],
                )
                if rules["metadata"]["size"]:
                    descriptor["size_bytes"] = len(resource.data)
                # Generic octet-stream is the only verified initial MIME; authored
                # labels/other MIME classification require a later provenance seam.
                if rules["metadata"]["mime"]:
                    descriptor["media_type"] = "application/octet-stream"
                if rules["metadata"]["digest"]:
                    descriptor["content_digest"] = dict(
                        algorithm="sha256", value=resource.revision
                    )
                resources.append(descriptor)
                if len(resources) > 16:
                    raise ResourceFailure("RESOURCE_LIMIT")
            if fingerprint(self.config_loader(context)) != fingerprint(config):
                raise ResourceFailure()
            # Prevent partial mixed-source discovery if a later read retired one.
            for descriptor in resources:
                _, _, current_tokens, _ = self._resolved(
                    workspace, descriptor["resource_ref"], context, False
                )
                if current_tokens != (
                    descriptor["source_revision"],
                    descriptor["resource_revision"],
                ):
                    raise ResourceFailure("STALE_REVISION")
            if fingerprint(self.config_loader(context)) != fingerprint(config):
                raise ResourceFailure()
            result = dict(contract_version="1", resources=resources)
            if len(json.dumps(result).encode()) > 32768:
                raise ResourceFailure("RESOURCE_LIMIT")
            return result
        except (BindingUnavailable, ValueError, OSError, UnicodeError) as exc:
            if isinstance(exc, ResourceFailure):
                raise
            raise ResourceFailure() from None

    def read(self, workspace, reference, source_revision, resource_revision, context):
        try:
            _, snapshot, tokens, _ = self._resolved(workspace, reference, context, True)
            if tokens != (source_revision, resource_revision):
                raise ResourceFailure("STALE_REVISION")
            return snapshot
        except (BindingUnavailable, ValueError, OSError, UnicodeError) as exc:
            if isinstance(exc, ResourceFailure):
                raise
            raise ResourceFailure() from None
