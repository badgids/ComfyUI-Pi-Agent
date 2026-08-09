from __future__ import annotations

import ast
import operator
import os
import platform
import random
import sys
import time
from typing import Any

from ..catalog import FL_MCP_COMPAT_TOOL_NAMES, FAMILIES
from ..runtime_context import read_runtime_context, runtime_paths_snapshot
from ..security import capability_audit

_BIN = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul, ast.Div: operator.truediv, ast.FloorDiv: operator.floordiv, ast.Mod: operator.mod, ast.Pow: operator.pow}
_UN = {ast.UAdd: operator.pos, ast.USub: operator.neg}


def _calc(expr: str) -> float | int:
    tree = ast.parse(str(expr), mode="eval")
    def ev(node: ast.AST):
        if isinstance(node, ast.Expression): return ev(node.body)
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)): return node.value
        if isinstance(node, ast.BinOp) and type(node.op) in _BIN: return _BIN[type(node.op)](ev(node.left), ev(node.right))
        if isinstance(node, ast.UnaryOp) and type(node.op) in _UN: return _UN[type(node.op)](ev(node.operand))
        raise ValueError("Only numeric literals and basic arithmetic operators are allowed.")
    value = ev(tree)
    if isinstance(value, float) and (value != value or abs(value) == float("inf")): raise ValueError("Non-finite result")
    return value


async def invoke(name: str, p: dict[str, Any], ctx: Any) -> Any:
    if name == "calculate_expressions":
        expressions = p.get("expressions") or p.get("items") or p.get("request") or []
        if isinstance(expressions, str): expressions = [expressions]
        return {"results": [{"expression": str(expr), "result": _calc(str(expr))} for expr in expressions]}
    if name == "wait":
        delay = max(0.0, min(float(p.get("delay", p.get("seconds", 1.0)) or 0), 60.0)); time.sleep(delay); return {"waited_for": delay}
    if name == "generate_seed": return {"seed": random.SystemRandom().randrange(0, 2**63 - 1)}
    if name == "generate_float":
        low, high = float(p.get("min", 0.0)), float(p.get("max", 1.0)); return {"value": random.SystemRandom().uniform(low, high)}
    if name == "generate_int":
        low, high = int(p.get("min", 0)), int(p.get("max", 100)); return {"value": random.SystemRandom().randint(low, high)}
    if name == "random_choice":
        items = list(p.get("items") or p.get("choices") or []); return {"value": random.SystemRandom().choice(items)} if items else {"success": False, "error": "No choices supplied."}
    if name == "get_system_info":
        return {"platform": platform.platform(), "python": sys.version, "python_executable": sys.executable, "cwd": os.getcwd(), "runtime_paths": runtime_paths_snapshot()}
    if name == "mcp_capability_audit":
        return {"success": True, "compatibility": {"fl_mcp_tool_count": len(FL_MCP_COMPAT_TOOL_NAMES), "families": list(FAMILIES), "dynamic_exposure": True}, "runtime": read_runtime_context(), "browser": ctx.browser.frontend_status(), "safety": capability_audit(ctx.safety)}
    raise KeyError(name)
