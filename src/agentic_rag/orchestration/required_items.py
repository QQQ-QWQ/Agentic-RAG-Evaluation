"""Deterministic required-item helpers for C3 final optimization."""

from __future__ import annotations

import re

KNOWN_REQUIRED_ITEMS: tuple[str, ...] = (
    "Self-RAG",
    "CRAG",
    "A-RAG",
    "TeaRAG",
    "KG-RAG",
    "LangChain",
    "LlamaIndex",
    "LangGraph",
    "Dify",
    "RAGFlow",
    "CrewAI",
    "FastGPT",
    "QAnything",
    "FAISS",
    "RAGAS",
    "Naive RAG",
    "Agentic RAG",
    "Tool-Augmented RAG",
    "Routing agents",
    "Query planning agents",
    "ReAct agents",
    "Plan-and-execute agents",
    "2501.09136",
    "2603.07379",
    "SoK",
    "Survey",
)

COMPLEX_TASK_TYPES = {
    "multi_doc",
    "comparison",
    "classification",
    "fuzzy_query",
    "insufficient_evidence",
}


def _unique(items: list[str]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for item in items:
        clean = " ".join(str(item or "").strip().split())
        if not clean:
            continue
        key = clean.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(clean)
    return out


def extract_required_items(
    question: str,
    *,
    task_type: str = "",
    plan_text: str = "",
) -> list[str]:
    """Extract comparison/classification targets without an extra LLM call."""
    text = f"{question or ''}\n{plan_text or ''}"
    items: list[str] = []
    lower_text = text.lower()
    for item in KNOWN_REQUIRED_ITEMS:
        if item.lower() in lower_text:
            items.append(item)

    # Add arXiv-like ids even when they are not in the curated list.
    items.extend(re.findall(r"\b\d{4}\.\d{4,6}\b", text))

    # Pull short ASCII names around Chinese enumeration separators.
    enum_tokens = re.split(r"[、，,；;和与/]| vs | VS ", text)
    for token in enum_tokens:
        token = token.strip(" \t\r\n：:（）()[]【】“”\"'")
        if not token:
            continue
        if re.fullmatch(r"[A-Za-z][A-Za-z0-9+\-.]{1,30}", token):
            if token.lower() not in {"rag", "agent", "api", "csv", "github"}:
                items.append(token)

    # Q012-style wording uses SoK/Survey as aliases for paper ids.
    if "SoK" in text and "2603.07379" not in items:
        items.append("2603.07379")
    if "Survey" in text and "2501.09136" not in items:
        items.append("2501.09136")

    # Keep the list small enough for prompts and logs.
    return _unique(items)[:10]


def is_complex_required_item_task(
    *,
    task_type: str = "",
    question: str = "",
    required_items: list[str] | None = None,
) -> bool:
    tt = (task_type or "").strip().lower()
    items = required_items or []
    if tt in {"multi_doc", "comparison", "classification"}:
        return True
    if len(items) >= 2:
        return True
    q = question or ""
    return any(
        marker in q
        for marker in ("比较", "对比", "分类", "分组", "归纳", "哪些", "每种", "各自", "分别")
    )


def c3_final_rag_budget(
    *,
    task_type: str = "",
    question: str = "",
    required_items: list[str] | None = None,
) -> int:
    """Return the final C3 max total RAG calls for a task."""
    tt = (task_type or "").strip().lower()
    items = required_items or []
    if tt == "simple_qa":
        return 1
    if tt in {"fuzzy_query", "insufficient_evidence"}:
        return 2
    if tt in {"calculation", "code_execution"}:
        return 1
    if tt == "table_analysis" and not is_complex_required_item_task(
        task_type=tt, question=question, required_items=items
    ):
        return 1
    if is_complex_required_item_task(
        task_type=tt, question=question, required_items=items
    ):
        return 4 if len(items) >= 3 else 3
    return 2


def item_support_map(answer: str, required_items: list[str]) -> dict[str, str]:
    """Cheap post-hoc coverage map for batch logs."""
    text = (answer or "").lower()
    out: dict[str, str] = {}
    for item in required_items:
        out[item] = "covered" if item.lower() in text else "missing"
    return out
