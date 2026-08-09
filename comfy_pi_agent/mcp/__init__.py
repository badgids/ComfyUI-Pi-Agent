"""Optional MCP-compatible services for ComfyUI-Pi.

The core ComfyUI plugin has no mandatory MCP dependency.  The stdio server and Pi
bridge are dependency-free adapters over the same service/runtime layer.
"""
from .catalog import FL_MCP_COMPAT_TOOL_NAMES, TOOL_SPECS, search_tools, route_text

__all__ = ["FL_MCP_COMPAT_TOOL_NAMES", "TOOL_SPECS", "search_tools", "route_text"]
