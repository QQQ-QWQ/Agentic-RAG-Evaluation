"""火山方舟多模态向量 API（纯文本项）：POST .../embeddings/multimodal。

文档：https://www.volcengine.com/docs/82379/1523520
纯文本时 input 为 [{\"type\":\"text\",\"text\":...}]，与 curl 示例一致。
"""

from __future__ import annotations

import httpx

from agentic_rag import config

_BATCH = 16

_QUERY_PREFIX = (
    "Instruct: Given a web search query, retrieve relevant passages that answer the "
    "query\nQuery: "
)


def _parse_embedding_payload(payload: object) -> list[list[float]]:
    """兼容 data 为 list（多条）或单 object（单条 embedding）。"""
    if payload is None:
        raise ValueError("响应缺少 data 字段")
    if isinstance(payload, list):
        ordered = sorted(
            payload,
            key=lambda x: x.get("index", 0) if isinstance(x, dict) else 0,
        )
        out: list[list[float]] = []
        for item in ordered:
            if isinstance(item, dict) and "embedding" in item:
                emb = item["embedding"]
                if isinstance(emb, list):
                    out.append([float(x) for x in emb])
        if out:
            return out
    if isinstance(payload, dict) and "embedding" in payload:
        emb = payload["embedding"]
        if isinstance(emb, list):
            return [[float(x) for x in emb]]
    raise ValueError(f"无法解析 embedding 结构: {type(payload)}")


def _mrl_truncate(vec: list[float], dim: int) -> list[float]:
    if dim <= 0:
        return vec
    if len(vec) <= dim:
        return vec
    return vec[:dim]


def _embed_one_batch(
    http: httpx.Client,
    url: str,
    headers: dict[str, str],
    batch: list[str],
    *,
    model: str,
    dimensions: int,
    encoding_format: str,
) -> list[list[float]]:
    body: dict = {
        "model": model,
        "input": [{"type": "text", "text": t} for t in batch],
        "encoding_format": encoding_format,
        "dimensions": dimensions,
    }
    r = http.post(url, headers=headers, json=body)
    if r.is_error:
        detail = (r.text or "")[:800]
        raise RuntimeError(
            f"方舟向量接口 HTTP {r.status_code}：{detail or r.reason_phrase}"
        )
    data = r.json()
    err = data.get("error")
    if err:
        raise RuntimeError(err)
    vecs = _parse_embedding_payload(data.get("data"))
    if len(vecs) == len(batch):
        return [_mrl_truncate(v, dimensions) for v in vecs]
    # 部分套餐单次只返回一条融合向量：逐条请求
    if len(batch) == 1:
        raise RuntimeError(
            f"期望 1 条向量，解析得到 {len(vecs)} 条，请检查接口响应格式"
        )
    out: list[list[float]] = []
    for t in batch:
        one = _embed_one_batch(
            http,
            url,
            headers,
            [t],
            model=model,
            dimensions=dimensions,
            encoding_format=encoding_format,
        )
        out.extend(one)
    return out


def embed_texts(
    texts: list[str],
    *,
    model: str | None = None,
    dimensions: int | None = None,
    is_query: bool = False,
    encoding_format: str = "float",
) -> list[list[float]]:
    """
    文本向量化：调用 `POST .../embeddings/multimodal`，每项为 {"type":"text","text":...}。
    `dimensions` 与官方一致，取 1024 或 2048（见环境变量 ARK_EMBEDDING_DIMENSIONS）。
    """
    if not texts:
        return []

    key = config.ARK_API_KEY
    if not key:
        raise ValueError("请配置环境变量 ARK_API_KEY")

    m = model or config.ARK_EMBEDDING_MODEL
    if not m:
        raise ValueError("请配置 ARK_EMBEDDING_MODEL（控制台 Model ID 或 Endpoint ID）")

    dim = dimensions if dimensions is not None else config.ARK_EMBEDDING_DIMENSIONS
    base = (config.ARK_BASE_URL or "").rstrip("/")
    url = f"{base}/embeddings/multimodal"

    to_embed = (
        texts if not is_query else [f"{_QUERY_PREFIX}{t}" for t in texts]
    )

    headers = {
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
    }

    all_vecs: list[list[float]] = []
    with httpx.Client(timeout=120.0) as http:
        for i in range(0, len(to_embed), _BATCH):
            batch = to_embed[i : i + _BATCH]
            vecs = _embed_one_batch(
                http,
                url,
                headers,
                batch,
                model=m,
                dimensions=dim,
                encoding_format=encoding_format,
            )
            all_vecs.extend(vecs)

    return all_vecs
