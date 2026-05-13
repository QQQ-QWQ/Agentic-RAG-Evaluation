"""本地运行偏好（非大模型记忆）：写入 ``configs/active_session.yaml``，合并进 ``RunProfile``。

与对话记忆无关；仅为 Chroma / 混合检索 / 改写 / rerank 等开关与数值的持久化。"""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

from agentic_rag.experiment.profile import RunProfile, merge_profile_dict


SCHEMA_VERSION = 1
SESSION_FILENAME = "active_session.yaml"
EXAMPLE_FILENAME = "active_session.example.yaml"


def repo_root() -> Path:
    """含 ``pyproject.toml`` 的仓库根目录。"""
    return Path(__file__).resolve().parents[3]


def default_session_path() -> Path:
    return repo_root() / "configs" / SESSION_FILENAME


def load_session_yaml_dict(path: Path) -> dict[str, Any] | None:
    """读取会话 YAML；不存在或无效则返回 None。"""
    if not path.is_file():
        return None
    import yaml

    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError):
        return None
    if not isinstance(raw, dict):
        return None
    return raw


def session_dict_for_profile(data: Mapping[str, Any]) -> dict[str, Any]:
    """去掉 schema 元字段，得到可传入 ``merge_profile_dict`` 的扁平 dict。"""
    skip = {"schema_version", "description"}
    out: dict[str, Any] = {}
    for k, v in data.items():
        if k in skip:
            continue
        out[str(k)] = v
    return out


def apply_active_session(profile: RunProfile, path: Path | None = None) -> bool:
    """若会话文件存在，合并进 ``profile``；返回是否发生过合并。"""
    p = path or default_session_path()
    data = load_session_yaml_dict(p)
    if not data:
        return False
    flat = session_dict_for_profile(data)
    merge_profile_dict(profile, flat)
    return True


def save_session_from_profile(profile: RunProfile, path: Path | None = None) -> Path:
    """将当前 ``RunProfile`` 写入会话文件。"""
    import yaml

    p = path or default_session_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    d = profile.to_dict()
    body: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "description": "本地运行偏好（非模型记忆）；rag / 工作台 [4] 自动合并（-c 与 CLI 可覆盖）",
    }
    for k, v in d.items():
        if k == "extra":
            continue
        body[k] = v
    p.write_text(yaml.safe_dump(body, allow_unicode=True, sort_keys=False), encoding="utf-8")
    return p


def interactive_configure_session() -> RunProfile:
    """终端交互：逐项确认模块开关，返回配置好的 ``RunProfile``。"""

    def yn(prompt: str, default: bool) -> bool:
        suf = "Y/n" if default else "y/N"
        raw = input(f"{prompt} [{suf}]: ").strip().lower()
        if not raw:
            return default
        return raw in ("y", "yes", "1", "true", "on")

    def num(prompt: str, default: int, min_v: int, max_v: int) -> int:
        raw = input(f"{prompt} [默认 {default}]: ").strip()
        if not raw:
            return default
        try:
            v = int(raw)
            return max(min_v, min(max_v, v))
        except ValueError:
            return default

    print()
    print("=== Topic4 运行偏好配置（写入本地 YAML，不是对话记忆）===")
    print("说明：以下选项决定单文档 RAG 默认行为；可用「工作台 [2]」或 session show 查看。")
    print()

    p = RunProfile()
    p.use_chroma_cache = yn("  [1] Chroma 向量缓存（关则每次向量化文档）", True)
    p.use_hybrid_retrieval = yn("  [2] 混合检索（BM25 + 稠密向量）", True)
    p.use_query_rewrite = yn("  [3] Query Rewrite（C1；关则接近 C0）", True)
    p.use_rerank = yn("  [4] 检索后 Rerank（耗 token）", False)
    if p.use_rerank:
        print("      rerank_backend: llm（默认）或稍后 YAML 修改")
    p.context_neighbor_chunks = num(
        "  [5] 邻接上下文扩展（每条命中向两侧扩展的 chunk 数，0 关闭）",
        0,
        0,
        8,
    )
    p.top_k = num("  Top-K（返回片段数）", 5, 1, 50)
    p.save_jsonl_log = yn("  是否默认写入 runs/logs JSONL", False)

    return p
