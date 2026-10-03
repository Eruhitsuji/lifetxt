"""Explicit compatibility bootstrap for CLI/Web/Remote surfaces."""

_bootstrapped = False


def bootstrap():
    global _bootstrapped
    if _bootstrapped:
        return
    # Mark before importing installers: several installers import legacy
    # package attributes while they are being initialized.
    _bootstrapped = True

    from .surface_runtime import install_runtime_contracts
    from .surface_runtime_compat import install_runtime_compatibility
    from .release_translation import install_release_translation_parser
    from .release_schema_extension import install_release_manifest_schema
    from .release_policy_compat import install_release_policy_compatibility
    from .release_manifest_validation import install_release_manifest_validation
    from .runtime_safety_v2 import install_runtime_safety_v2
    from .schema_validation_v2 import install_schema_validation_v2
    from .safety_compat_v2 import install_safety_compat_v2

    install_runtime_contracts()
    install_runtime_compatibility()
    install_release_translation_parser()
    install_release_manifest_schema()
    install_release_policy_compatibility()
    install_release_manifest_validation()
    install_runtime_safety_v2()
    install_schema_validation_v2()
    install_safety_compat_v2()

    for version in range(4, 32):
        module = __import__(
            f"lifetxt.schema_extensions_v{version}",
            fromlist=[f"install_schema_extensions_v{version}"],
        )
        getattr(module, f"install_schema_extensions_v{version}")()

    from .remote_contracts_v6 import install_remote_contracts_v6
    from .remote_compatibility_v21 import (
        install_remote_compatibility_v21,
        install_remote_client_compatibility_v21,
    )
    from .remote_web import install_remote_web
    from .remote_client import install_remote_client_cli
    from .remote_client_writes import install_remote_client_writes_cli
    from .remote_client_writes_compat_v25 import install_remote_client_writes_compat_v25
    from .ticket_project_surfaces import install_ticket_project_surfaces
    from .ticket_revision_writes import install_ticket_revision_writes
    from .ticket_custom_fields import install_ticket_custom_fields
    from .ticket_workflow_cli import install_ticket_workflow_cli
    from .ticket_planning_cli import install_ticket_planning_cli
    from .ticket_workflow_surfaces import install_ticket_workflow_surfaces
    from .remote_ticket_writes import install_remote_ticket_writes
    from .remote_item_writes import install_remote_item_writes

    install_remote_contracts_v6()
    install_remote_compatibility_v21()
    install_remote_client_compatibility_v21()
    install_remote_web()
    install_remote_client_cli()
    install_remote_client_writes_cli()
    install_remote_client_writes_compat_v25()
    install_ticket_project_surfaces()
    install_ticket_revision_writes()
    install_ticket_custom_fields()
    install_ticket_workflow_cli()
    install_ticket_planning_cli()
    install_ticket_workflow_surfaces()
    install_remote_ticket_writes()
    install_remote_item_writes()
