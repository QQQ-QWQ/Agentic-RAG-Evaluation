"""安全数值计算（对应开题 C4 calculator / 题集 calculation）。"""

from __future__ import annotations

import ast
import operator
from typing import Any

from agentic_rag.tools.response_format import tool_response_json

_ALLOWED_OPS: dict[type[ast.AST], Any] = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
    ast.USub: operator.neg,
    ast.UAdd: operator.pos,
}


def _safe_eval_node(node: ast.AST) -> float:
    if isinstance(node, ast.Constant):
        if isinstance(node.value, (int, float)):
            return float(node.value)
        raise ValueError(f"不支持的常量类型：{type(node.value).__name__}")
    if isinstance(node, ast.UnaryOp) and type(node.op) in _ALLOWED_OPS:
        return _ALLOWED_OPS[type(node.op)](_safe_eval_node(node.operand))
    if isinstance(node, ast.BinOp) and type(node.op) in _ALLOWED_OPS:
        return _ALLOWED_OPS[type(node.op)](
            _safe_eval_node(node.left),
            _safe_eval_node(node.right),
        )
    raise ValueError(f"不允许的表达式节点：{type(node).__name__}")


def safe_calculate(expression: str) -> dict[str, Any]:
    """仅允许数字与 + - * / // % ** 的算术表达式。"""
    expr = (expression or "").strip()
    if not expr:
        return {"ok": False, "error": "expression 为空"}
    if len(expr) > 2000:
        return {"ok": False, "error": "表达式过长"}
    try:
        tree = ast.parse(expr, mode="eval")
    except SyntaxError as exc:
        return {"ok": False, "error": f"语法错误：{exc}"}
    try:
        value = _safe_eval_node(tree.body)
    except (ValueError, ZeroDivisionError, OverflowError) as exc:
        return {"ok": False, "error": str(exc)}
    return {"ok": True, "expression": expr, "result": value}


def format_calculator_response(payload: dict[str, Any]) -> str:
    return tool_response_json(
        "topic4_calculator",
        ok=bool(payload.get("ok")),
        data={k: v for k, v in payload.items() if k not in ("ok", "error")},
        error=str(payload.get("error") or "") or None,
        hints=["仅用于数值运算；CSV 列统计请用 topic4_table_analyzer。"],
    )
