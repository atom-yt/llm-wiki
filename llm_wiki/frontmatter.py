"""YAML Front-matter 解析和操作

用于解析、修改和重新生成 Markdown 文件的 YAML front-matter。
"""
import re
from typing import Optional, Any
from datetime import datetime


class FrontMatter:
    """解析和操作 YAML front-matter"""

    def __init__(self, content: str):
        """
        Args:
            content: Markdown 文件内容（可能包含 front-matter）
        """
        self._original_content = content
        self._data: dict = {}
        self._raw_front_matter: str = ""
        self._parse()

    def _parse(self) -> None:
        """解析 YAML front-matter"""
        if not self._original_content.startswith("---"):
            return

        # 查找结束标记
        end_match = re.search(r'\n---\s*\n', self._original_content[3:])
        if not end_match:
            return

        end_pos = 3 + end_match.end()
        self._raw_front_matter = self._original_content[:end_pos]

        # 解析 YAML
        yaml_content = self._original_content[3:end_match.start() + 3].strip()
        if yaml_content:
            try:
                import yaml
                self._data = yaml.safe_load(yaml_content) or {}
            except Exception:
                self._data = {}

    def get(self, key: str, default: Any = None) -> Any:
        """获取 front-matter 中的值"""
        return self._data.get(key, default)

    def set(self, key: str, value: Any) -> None:
        """设置 front-matter 中的值"""
        self._data[key] = value

    def remove(self, key: str) -> None:
        """删除 front-matter 中的键"""
        self._data.pop(key, None)

    def add_source(self, source_name: str) -> None:
        """添加来源追踪"""
        sources = self.get("sources", [])
        if not isinstance(sources, list):
            sources = []
        if source_name not in sources:
            sources.append(source_name)
        self.set("sources", sources)
        self.set("updated_at", datetime.now().isoformat())

    def add_related(self, page_name: str) -> None:
        """添加相关页面"""
        related = self.get("related", [])
        if not isinstance(related, list):
            related = []
        if page_name not in related:
            related.append(page_name)
        self.set("related", related)

    @property
    def data(self) -> dict:
        """获取完整的 front-matter 数据"""
        return self._data.copy()

    @property
    def has_front_matter(self) -> bool:
        """是否有 front-matter"""
        return bool(self._data)

    @property
    def body(self) -> str:
        """获取 body 部分（不含 front-matter）"""
        if self._raw_front_matter:
            return self._original_content[len(self._raw_front_matter):]
        return self._original_content

    def render(self) -> str:
        """重新生成完整内容"""
        import yaml

        body = self.body

        if not self._data:
            # 没有 front-matter 数据，返回纯 body
            return body

        # 生成 YAML
        yaml_str = yaml.dump(self._data, sort_keys=False, allow_unicode=True)
        return f"---\n{yaml_str}---\n{body}"

    def render_with_new_body(self, new_body: str) -> str:
        """使用新的 body 重新生成完整内容"""
        import yaml

        if not self._data:
            return new_body

        yaml_str = yaml.dump(self._data, sort_keys=False, allow_unicode=True)
        return f"---\n{yaml_str}---\n{new_body}"

    @classmethod
    def create(cls, page_type: str, sources: list[str] = None,
               related: list[str] = None) -> "FrontMatter":
        """创建新的 front-matter"""
        fm = cls("")
        fm.set("type", page_type)
        if sources:
            fm.set("sources", sources)
        if related:
            fm.set("related", related)
        fm.set("created_at", datetime.now().isoformat())
        return fm

    def __repr__(self) -> str:
        return f"FrontMatter({self._data})"
