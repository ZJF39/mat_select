# -*- coding: utf-8 -*-
"""语义近似（契约 ADR-04：字符 n-gram 余弦，可插拔替换）。

对外只暴露 `EmbeddingProvider` 抽象与 `cosine()`；一期默认实现
`NgramEmbeddingProvider`（字符 bigram 集合余弦），无 GPU / 不联网即可运行。
二期若接入本地 bge，只需新增一个 Provider 子类并改 `get_provider()` 返回值，
打分逻辑零改动。
"""
from __future__ import annotations

import math
from collections import Counter
from typing import Dict


class EmbeddingProvider:
    """向量化提供者抽象：文本 → 稀疏向量（token → 权重）。"""

    name = "abstract"

    def embed(self, text: str) -> Dict[str, float]:  # pragma: no cover - 抽象
        raise NotImplementedError


class NgramEmbeddingProvider(EmbeddingProvider):
    """字符 bigram 集合余弦（对中文子串/缩写友好）。"""

    name = "ngram-bigram"

    def __init__(self, n: int = 2):
        self.n = max(1, int(n))

    def embed(self, text: str) -> Dict[str, float]:
        if not text:
            return {}
        # 归一化：去空白、统一小写；中英文/数字都按字符切 n-gram
        s = "".join(str(text).lower().split())
        if not s:
            return {}
        grams = [s[i:i + self.n] for i in range(max(1, len(s) - self.n + 1))]
        return dict(Counter(grams))


_DEFAULT_PROVIDER: EmbeddingProvider = NgramEmbeddingProvider(2)


def get_provider() -> EmbeddingProvider:
    """当前生效的语义 Provider（ADR-04 的可替换点）。"""
    return _DEFAULT_PROVIDER


def cosine(a: Dict[str, float], b: Dict[str, float]) -> float:
    """稀疏向量余弦相似度，返回 0~1（任一为空 → 0）。"""
    if not a or not b:
        return 0.0
    shared = set(a) & set(b)
    if not shared:
        return 0.0
    dot = sum(a[k] * b[k] for k in shared)
    na = math.sqrt(sum(v * v for v in a.values()))
    nb = math.sqrt(sum(v * v for v in b.values()))
    if na == 0 or nb == 0:
        return 0.0
    return max(0.0, min(1.0, dot / (na * nb)))


def similarity(text_a: str, text_b: str) -> float:
    """便捷函数：两段文本的语义近似分（0~1）。"""
    p = _DEFAULT_PROVIDER
    return cosine(p.embed(text_a), p.embed(text_b))
