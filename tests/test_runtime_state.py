"""AppStateStore 与副作用分发测试。"""

from __future__ import annotations

from agentic_rag.runtime.state.app_state import AppState, PermissionState
from agentic_rag.runtime.state.store import AppStateStore


def test_tier_change_sets_ui_hint():
    from dataclasses import replace

    store = AppStateStore(AppState(tier="c3"))
    store.set_state(replace(store.get_state(), tier="c4"), reason="test")
    st = store.get_state()
    assert st.tier == "c4"
    assert st.ui_hint


def test_store_changelog():
    store = AppStateStore()
    store.set_state(store.get_state(), reason="init")
    assert len(store.changelog()) >= 1


def test_c4_permission_effect():
    from dataclasses import replace

    store = AppStateStore(AppState(permissions=PermissionState(enable_c4_tools=False)))
    old = store.get_state()
    new = replace(
        old,
        permissions=replace(old.permissions, enable_c4_tools=True),
    )
    store.set_state(new, reason="toggle")
    assert store.get_state().ui_hint
