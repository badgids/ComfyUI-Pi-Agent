"""ComfyUI Pi Agent Production Suite entrypoint."""
from __future__ import annotations

import logging

WEB_DIRECTORY = "./web"

try:
    try:
        from .comfy_pi_agent.nodes import NODE_CLASS_MAPPINGS, NODE_DISPLAY_NAME_MAPPINGS
        from .comfy_pi_agent.routes import register_routes
    except ImportError:
        # Some custom-node loaders import a repository by file path instead of as a
        # normal parent package. The absolute fallback keeps that loader safe.
        from comfy_pi_agent.nodes import NODE_CLASS_MAPPINGS, NODE_DISPLAY_NAME_MAPPINGS
        from comfy_pi_agent.routes import register_routes
    try:
        register_routes()
    except Exception as route_error:
        logging.getLogger(__name__).warning("Pi Agent routes were not registered: %s", route_error)
except Exception as exc:
    logging.getLogger(__name__).exception("ComfyUI Pi Agent failed to load safely: %s", exc)
    NODE_CLASS_MAPPINGS = {}
    NODE_DISPLAY_NAME_MAPPINGS = {}

__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS", "WEB_DIRECTORY"]
