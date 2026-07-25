"""Parser and CLI utilities for the life.txt format."""

__version__ = "0.1.0"

from .model import Diagnostic, Item
from .parser import parse_line, parse_text
from .serializer import item_to_line, items_to_json, items_to_jsonl

# Connect the shared CAS layer to public Web and MCP requests. Installation is
# dependency-free: FastAPI is still imported only when create_app() is called.
from .surface_runtime import install_runtime_contracts as _install_runtime_contracts
from .surface_runtime_compat import (
    install_runtime_compatibility as _install_runtime_compatibility,
)

_install_runtime_contracts()
_install_runtime_compatibility()
del _install_runtime_contracts
del _install_runtime_compatibility

# Release checks must behave identically on compact/generated markup and on
# Python 3.10, where tomllib is not part of the standard library. Keep these
# compatibility adapters dependency-free; the strict release job still installs
# jsonschema/build/twine for publication-only validation.
from .release_translation import (
    install_release_translation_parser as _install_release_translation_parser,
)
from .release_schema_extension import (
    install_release_manifest_schema as _install_release_manifest_schema,
)
from .release_policy_compat import (
    install_release_policy_compatibility as _install_release_policy_compatibility,
)
from .release_manifest_validation import (
    install_release_manifest_validation as _install_release_manifest_validation,
)

_install_release_translation_parser()
_install_release_manifest_schema()
_install_release_policy_compatibility()
_install_release_manifest_validation()
del _install_release_translation_parser
del _install_release_manifest_schema
del _install_release_policy_compatibility
del _install_release_manifest_validation

# Apply the next P0/P1 safety layer after the compatibility and release-policy
# adapters exist. This keeps the package dependency-free while adding persistent
# revision telemetry, explicit timezone contexts, workspace diagnostics,
# compensated multi-target operations, and the expanded schema bundle.
from .runtime_safety_v2 import install_runtime_safety_v2 as _install_runtime_safety_v2
from .schema_validation_v2 import install_schema_validation_v2 as _install_schema_validation_v2
from .safety_compat_v2 import install_safety_compat_v2 as _install_safety_compat_v2

_install_runtime_safety_v2()
_install_schema_validation_v2()
_install_safety_compat_v2()
from .schema_extensions_v4 import install_schema_extensions_v4 as _install_schema_extensions_v4
_install_schema_extensions_v4()
del _install_schema_extensions_v4
from .schema_extensions_v5 import install_schema_extensions_v5 as _install_schema_extensions_v5
_install_schema_extensions_v5()
del _install_schema_extensions_v5
from .schema_extensions_v6 import install_schema_extensions_v6 as _install_schema_extensions_v6
_install_schema_extensions_v6()
del _install_schema_extensions_v6
from .schema_extensions_v7 import install_schema_extensions_v7 as _install_schema_extensions_v7
_install_schema_extensions_v7()
del _install_schema_extensions_v7
from .schema_extensions_v8 import install_schema_extensions_v8 as _install_schema_extensions_v8
_install_schema_extensions_v8()
del _install_schema_extensions_v8
from .schema_extensions_v9 import install_schema_extensions_v9 as _install_schema_extensions_v9
_install_schema_extensions_v9()
del _install_schema_extensions_v9
from .schema_extensions_v10 import install_schema_extensions_v10 as _install_schema_extensions_v10
_install_schema_extensions_v10()
del _install_schema_extensions_v10
from .schema_extensions_v11 import install_schema_extensions_v11 as _install_schema_extensions_v11
_install_schema_extensions_v11()
del _install_schema_extensions_v11
from .schema_extensions_v12 import install_schema_extensions_v12 as _install_schema_extensions_v12
_install_schema_extensions_v12()
del _install_schema_extensions_v12
from .schema_extensions_v13 import install_schema_extensions_v13 as _install_schema_extensions_v13
_install_schema_extensions_v13()
del _install_schema_extensions_v13
from .schema_extensions_v14 import install_schema_extensions_v14 as _install_schema_extensions_v14
_install_schema_extensions_v14()
del _install_schema_extensions_v14
from .schema_extensions_v15 import install_schema_extensions_v15 as _install_schema_extensions_v15
_install_schema_extensions_v15()
del _install_schema_extensions_v15
from .schema_extensions_v16 import install_schema_extensions_v16 as _install_schema_extensions_v16
_install_schema_extensions_v16()
del _install_schema_extensions_v16
from .remote_contracts_v6 import install_remote_contracts_v6 as _install_remote_contracts_v6
_install_remote_contracts_v6()
del _install_remote_contracts_v6
from .ticket_project_surfaces import install_ticket_project_surfaces as _install_ticket_project_surfaces
_install_ticket_project_surfaces()
del _install_ticket_project_surfaces
from .ticket_revision_writes import install_ticket_revision_writes as _install_ticket_revision_writes
_install_ticket_revision_writes()
del _install_ticket_revision_writes
del _install_runtime_safety_v2
del _install_schema_validation_v2
del _install_safety_compat_v2

__all__ = [
    "Diagnostic",
    "Item",
    "item_to_line",
    "items_to_json",
    "items_to_jsonl",
    "parse_line",
    "parse_text",
]
