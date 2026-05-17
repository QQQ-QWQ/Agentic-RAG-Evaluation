"""状态副作用集中分发（禁止在 UI 层散落）。"""

from __future__ import annotations

from agentic_rag.runtime.state.app_state import AppState


def on_change_app_state(old: AppState, new: AppState, *, reason: str) -> None:
    if old.tier != new.tier:
        _on_tier_change(old, new, reason=reason)
    if old.permissions.enable_c4_tools != new.permissions.enable_c4_tools:
        _on_c4_toggle(old, new, reason=reason)
    if old.session.cli_doc != new.session.cli_doc:
        _on_doc_bound(old, new, reason=reason)


def _on_tier_change(old: AppState, new: AppState, *, reason: str) -> None:
    new.ui_hint = f"档位已切换为 {new.tier.upper()}（{reason}）"


def _on_c4_toggle(old: AppState, new: AppState, *, reason: str) -> None:
    if new.permissions.enable_c4_tools:
        new.ui_hint = "C4 工具已启用（入库 / MarkItDown / 可选沙箱）"
    else:
        new.ui_hint = "C3 模式：仅检索工具"


def _on_doc_bound(old: AppState, new: AppState, *, reason: str) -> None:
    if new.session.cli_doc:
        new.ui_hint = f"已绑定文档：{new.session.cli_doc}"
