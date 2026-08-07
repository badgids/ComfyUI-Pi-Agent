"""Lazy third-party ComfyUI integration registry.

The package intentionally does not import individual node-pack adapters here. Importing this
module at ComfyUI startup stays small; integration modules and detailed knowledge are loaded
only by the router when a workflow/message matches or a user calls an integration node.
"""

from .router import (
    build_dynamic_integration_context,
    integration_status,
    load_integration_registry,
    load_integration_module,
    match_integrations,
)

__all__ = [
    "build_dynamic_integration_context",
    "integration_status",
    "load_integration_registry",
    "load_integration_module",
    "match_integrations",
]
