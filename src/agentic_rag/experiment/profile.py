"""单次 RAG 运行配置：各模块用开关组合，默认尽量接通当前已实现能力；与底层实现解耦。"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Literal

TokenizerName = Literal["bigram", "jieba", "default"]


def _coerce_bool(value: Any, default: bool) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return bool(value)


@dataclass
class RunProfile:
    """
    ``experiment.runner.run_document_rag`` 使用的运行参数。

    - ``use_chroma_cache``：Chroma 读写；关则每次全量向量化（仅内存）。
    - ``use_hybrid_retrieval``：稠密 + BM25 融合；关则仅稠密。
    - ``use_query_rewrite``：C1（改写 + 多检索）；关则 C0。
    """

    use_chroma_cache: bool = True
    use_hybrid_retrieval: bool = True
    use_query_rewrite: bool = True

    use_rerank: bool = False
    rerank_backend: str = "llm"
    rerank_pool_size: int = 20
    context_neighbor_chunks: int = 0

    dense_weight: float = 0.6
    bm25_weight: float = 0.4
    bm25_tokenizer: TokenizerName = "bigram"

    top_k: int = 5
    question_id: str = ""

    rewrite_prompt_file: Path | None = None

    save_jsonl_log: bool = False
    log_dir: str | Path = "runs/logs"

    extra: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["rewrite_prompt_file"] = (
            str(self.rewrite_prompt_file) if self.rewrite_prompt_file else None
        )
        return d


def resolve_bm25_tokenizer(name: TokenizerName) -> Callable[[str], list[str]]:
    from agentic_rag.rag.bm25 import (
        chinese_bigram_tokenize,
        default_tokenize,
        jieba_tokenize,
    )

    if name == "jieba":
        return jieba_tokenize
    if name == "default":
        return default_tokenize
    return chinese_bigram_tokenize


def merge_profile_dict(base: RunProfile, data: Mapping[str, Any]) -> None:
    """用扁平字典原地更新 profile。"""
    if "use_chroma_cache" in data:
        base.use_chroma_cache = _coerce_bool(data["use_chroma_cache"], True)
    if "use_hybrid_retrieval" in data:
        base.use_hybrid_retrieval = _coerce_bool(data["use_hybrid_retrieval"], True)
    if "use_query_rewrite" in data:
        base.use_query_rewrite = _coerce_bool(data["use_query_rewrite"], True)
    if "dense_weight" in data:
        base.dense_weight = float(data["dense_weight"])
    if "bm25_weight" in data:
        base.bm25_weight = float(data["bm25_weight"])
    if "bm25_tokenizer" in data:
        t = str(data["bm25_tokenizer"]).strip().lower()
        if t in ("bigram", "jieba", "default"):
            base.bm25_tokenizer = t  # type: ignore[assignment]
    if "top_k" in data:
        base.top_k = int(data["top_k"])
    if "use_rerank" in data:
        base.use_rerank = _coerce_bool(data["use_rerank"], False)
    if "rerank_backend" in data:
        base.rerank_backend = str(data["rerank_backend"]).strip().lower()
    if "rerank_pool_size" in data:
        base.rerank_pool_size = int(data["rerank_pool_size"])
    if "context_neighbor_chunks" in data:
        base.context_neighbor_chunks = int(data["context_neighbor_chunks"])
    if "question_id" in data:
        base.question_id = str(data["question_id"])
    if "rewrite_prompt_file" in data and data["rewrite_prompt_file"]:
        base.rewrite_prompt_file = Path(str(data["rewrite_prompt_file"]))
    if "save_jsonl_log" in data:
        base.save_jsonl_log = _coerce_bool(data["save_jsonl_log"], False)
    if "log_dir" in data:
        base.log_dir = data["log_dir"]


def apply_modules_yaml(base: RunProfile, modules: Mapping[str, Any]) -> None:
    """兼容 ``configs/c1_rewrite.yaml`` 等文件中的 ``modules:`` 块。"""
    if "hybrid_retrieval" in modules:
        base.use_hybrid_retrieval = _coerce_bool(modules["hybrid_retrieval"], True)
    if "query_rewrite" in modules:
        base.use_query_rewrite = _coerce_bool(modules["query_rewrite"], True)


def load_profile_yaml(path: Path) -> RunProfile:
    import yaml

    raw = path.read_text(encoding="utf-8")
    data = yaml.safe_load(raw) or {}
    if not isinstance(data, dict):
        return RunProfile()
    return profile_from_yaml_dict(data)


def profile_from_yaml_dict(data: Mapping[str, Any]) -> RunProfile:
    p = RunProfile()
    if "modules" in data and isinstance(data["modules"], dict):
        apply_modules_yaml(p, data["modules"])
    merge_profile_dict(p, data)
    if "retrieval" in data and isinstance(data["retrieval"], dict):
        r = data["retrieval"]
        if "top_k" in r:
            p.top_k = int(r["top_k"])
        if "use_rerank" in r:
            p.use_rerank = _coerce_bool(r["use_rerank"], False)
        if "rerank_backend" in r:
            p.rerank_backend = str(r["rerank_backend"]).strip().lower()
        if "rerank_pool_size" in r:
            p.rerank_pool_size = int(r["rerank_pool_size"])
        if "context_neighbor_chunks" in r:
            p.context_neighbor_chunks = int(r["context_neighbor_chunks"])
    if "query_rewrite" in data and isinstance(data["query_rewrite"], dict):
        qr = data["query_rewrite"]
        if "prompt_file" in qr and qr["prompt_file"]:
            p.rewrite_prompt_file = Path(str(qr["prompt_file"]))
    if "logging" in data and isinstance(data["logging"], dict):
        lg = data["logging"]
        if "save_jsonl" in lg:
            p.save_jsonl_log = _coerce_bool(lg["save_jsonl"], False)
    return p
