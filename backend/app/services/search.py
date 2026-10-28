"""书籍检索：FTS5(trigram) 与 LIKE 的取舍。

`books_fts` 用 trigram 分词（见迁移 0007），中文可以按任意子串命中，
但 **查询词必须至少 3 个字符** 才会产生 trigram。所以按词拆分处理：

- 长度 ≥3 的词：拼进一个 FTS5 `MATCH` 表达式（词之间 AND）
- 长度 1–2 的词（「三体」「猫腻」）：trigram 查不出结果，退回 `LIKE %x%`
- 两类条件在 SQL 里以 AND 组合，所以「刘慈欣 闪电」这种混搭也能查

`LIKE` 路径在十万行时约 40ms（全表扫描），对单机 NAS 仍可接受；
真正的加速点在于长标题/多字段组合搜索。
"""

from __future__ import annotations

import re

MIN_TERM_CHARS = 3

_SPLIT = re.compile(r"\s+")


def search_plan(query: str | None) -> tuple[str | None, list[str]]:
    """把用户输入拆成 (FTS 表达式, 需要 LIKE 的短词)。

    - FTS 表达式为 None 表示没有足够长的词
    - 每个词包成短语并转义双引号，避免 `*`、`-`、`OR` 之类被当成语法
    """
    if not query:
        return None, []

    terms = [term for term in _SPLIT.split(query.strip()) if term]
    if not terms:
        return None, []

    long_terms = [term for term in terms if len(term) >= MIN_TERM_CHARS]
    short_terms = [term for term in terms if len(term) < MIN_TERM_CHARS]

    if not long_terms:
        return None, short_terms

    escaped = ['"' + term.replace('"', '""') + '"' for term in long_terms]
    return " AND ".join(escaped), short_terms
