"""页面合并策略

支持多种策略来合并现有页面和新内容。
"""
from enum import Enum
from datetime import datetime


class MergeStrategy(Enum):
    """页面合并策略"""
    APPEND = "append"      # 在末尾添加
    PREPEND = "prepend"    # 在开头添加（用于最新发现）
    MERGE = "merge"        # 智能合并，保留原有内容
    REPLACE = "replace"     # 完全覆盖


def merge_pages(
    existing: str,
    new: str,
    strategy: MergeStrategy,
    source_name: str
) -> str:
    """按策略合并页面内容

    Args:
        existing: 现有页面内容
        new: 新内容
        strategy: 合并策略
        source_name: 来源名称，用于标注

    Returns:
        合并后的内容
    """
    if strategy == MergeStrategy.REPLACE:
        return new

    if strategy == MergeStrategy.APPEND:
        # 在现有内容后追加，带分隔符和来源标注
        timestamp = datetime.now().strftime("%Y-%m-%d")
        return f"""{existing}

---

## Update from {source_name} ({timestamp})

{new}
"""

    if strategy == MergeStrategy.PREPEND:
        # 在开头添加新内容
        timestamp = datetime.now().strftime("%Y-%m-%d")
        return f"""## Latest from {source_name} ({timestamp})

{new}

---

{existing}
"""

    if strategy == MergeStrategy.MERGE:
        # LLM 辅助的智能合并
        return _llm_merge(existing, new, source_name)

    # 默认：合并
    return _llm_merge(existing, new, source_name)


def _llm_merge(existing: str, new: str, source_name: str) -> str:
    """使用 LLM 智能合并内容

    注意：此函数需要 LLMClient，在调用时注入
    """
    prompt = f"""Merge the two markdown contents below intelligently.

Existing content:
```
{existing}
```

New content from {source_name}:
```
{new}
```

Instructions:
- Preserve information from both sources
- Remove duplicates
- Resolve contradictions by keeping the new content
- Add a note at the top mentioning this was updated from {source_name}
- Keep the original structure and formatting
- Return only the merged markdown content, no explanations

Return only the merged markdown content."""
    return prompt  # 实际使用时会传递给 LLM


def parse_strategy(strategy_str: str) -> MergeStrategy:
    """解析策略字符串"""
    strategy_str = strategy_str.lower()
    for s in MergeStrategy:
        if s.value == strategy_str:
            return s
    return MergeStrategy.MERGE  # 默认合并策略
