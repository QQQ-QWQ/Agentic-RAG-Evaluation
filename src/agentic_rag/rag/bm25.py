"""Okapi BM25 稀疏检索（纯 Python，无第三方检索依赖）。

默认 ``default_tokenize`` 按空白切分，适合英文；中文无空格边界，需换用下面任一策略：

- **词级（推荐）**：``jieba_tokenize``，需 ``pip install jieba``。
- **零依赖折中**：``chinese_bigram_tokenize``（相邻字二元组，检索基线可用）。

混合检索在 ``pipelines.local_rag.retrieve_with_index`` 中通过 ``fusion`` 模块与稠密分数融合；也可单独用于实验。
"""

from __future__ import annotations

import math
import re
from collections import defaultdict
from collections.abc import Callable


def default_tokenize(text: str) -> list[str]:
    """英文友好：空白切分 + 小写。中文需替换为分词函数。"""
    return text.lower().split()


# --- 中文 BM25：词袋须有「词」边界，不能整句当一个 token ---


def chinese_bigram_tokenize(text: str) -> list[str]:
    """
    去空白后做 **汉字/字符二元组**（例：「红岩网校」→「红岩」「岩网」「网校」）。

    无额外依赖，适合快速实验；语义不如分词，但比 ``split()`` 整句一块要好得多。
    """
    s = re.sub(r"\s+", "", text.strip())
    if len(s) <= 1:
        return list(s)
    return [s[i : i + 2] for i in range(len(s) - 1)]


def chinese_char_tokenize(text: str) -> list[str]:
    """按 **单字** 切分（去掉空白）。比二元组更稀，短查询时可试。"""
    return list(re.sub(r"\s+", "", text.strip()))


def jieba_tokenize(text: str, *, cut_all: bool = False) -> list[str]:
    """
    **结巴分词**，得到词级 token，BM25 中文场景首选。

    需安装：``pip install jieba``（未安装时抛出 ``ImportError`` 并提示命令）。
    """
    try:
        import jieba  # type: ignore[import-untyped]
    except ImportError as e:
        raise ImportError(
            "中文词级 BM25 需要 jieba：pip install jieba"
        ) from e
    return list(jieba.cut(text.strip(), cut_all=cut_all))


class BM25Index:
    """
    对一组文档串（通常为同一文档的分块）建立 BM25，支持打分与 Top-K。

    参数 ``k1``、``b`` 为经典 Okapi BM25 超参；文档为空时使用平滑避免除零。
    """

    def __init__(
        self,
        documents: list[str],
        *,
        k1: float = 1.5,
        b: float = 0.75,
        tokenize: Callable[[str], list[str]] = default_tokenize,
    ) -> None:
        if k1 < 0 or b < 0 or b > 1:
            raise ValueError("需满足 k1>=0 且 0<=b<=1")
        self.documents = documents
        self.k1 = k1
        self.b = b
        self.tokenize = tokenize
        self._n = len(documents)
        self._doc_tf: list[dict[str, int]] = []
        self._doc_len: list[int] = []
        self._df: dict[str, int] = {}
        self._avgdl: float = 0.0
        self._build()

    def _build(self) -> None:
        dl_total = 0
        df_count: dict[str, int] = defaultdict(int)

        for doc in self.documents:
            terms = self.tokenize(doc)
            tf: dict[str, int] = defaultdict(int)
            for t in terms:
                tf[t] += 1
            seen = set(tf.keys())
            for t in seen:
                df_count[t] += 1
            self._doc_tf.append(dict(tf))
            ln = len(terms)
            self._doc_len.append(ln)
            dl_total += ln

        self._df = dict(df_count)
        self._avgdl = dl_total / self._n if self._n else 0.0

    def _idf(self, term: str) -> float:
        n = self._df.get(term, 0)
        # Robertson–Walker IDF，与常见 rank_bm25 实现一致
        return math.log((self._n - n + 0.5) / (n + 0.5) + 1.0)

    def scores(self, query: str) -> list[float]:
        """对每个文档返回 BM25 分数（与 ``documents`` 同序）。"""
        q_terms = self.tokenize(query)
        out = [0.0] * self._n
        avgdl = self._avgdl if self._avgdl > 0 else 1.0

        for i in range(self._n):
            dl = self._doc_len[i]
            norm_dl = dl / avgdl if avgdl > 0 else 1.0
            denom_base = self.k1 * (1.0 - self.b + self.b * norm_dl)
            tf_map = self._doc_tf[i]
            s = 0.0
            for term in q_terms:
                if term not in tf_map:
                    continue
                tf = tf_map[term]
                idf = self._idf(term)
                denom = tf + denom_base
                if denom <= 0:
                    continue
                s += idf * (tf * (self.k1 + 1.0)) / denom
            out[i] = s
        return out

    def top_k_indices(self, query: str, k: int = 4) -> list[tuple[int, float]]:
        """返回分数最高的前 ``k`` 条 ``(文档下标, 分数)``。"""
        if k <= 0:
            return []
        sc = self.scores(query)
        order = sorted(range(len(sc)), key=lambda i: sc[i], reverse=True)
        return [(i, sc[i]) for i in order[:k]]

    def top_k(self, query: str, k: int = 4) -> list[tuple[str, float]]:
        """返回 ``(文档文本, 分数)``，便于与 ``SimpleVectorIndex.top_k`` 风格对齐。"""
        return [(self.documents[i], s) for i, s in self.top_k_indices(query, k)]
