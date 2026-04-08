"""矛盾检测和标记

检测 Wiki 页面间的矛盾并添加标记。
"""
import re
from typing import List, Dict, Optional


class ContradictionMarker:
    """检测和标记页面间的矛盾"""

    def __init__(self, wiki, llm):
        self.wiki = wiki
        self.llm = llm

    def check_pages(self, page_names: List[str]) -> List[Dict]:
        """检查指定页面间的矛盾

        Args:
            page_names: 要检查的页面名称列表

        Returns:
            矛盾列表，每个矛盾包含 description, pages, severity
        """
        if len(page_names) < 2:
            return []

        # 读取页面内容
        contents = []
        for name in page_names:
            try:
                content = self.wiki.read_wiki_page(name)
                contents.append(f"### {name}.md\n{content}")
            except FileNotFoundError:
                contents.append(f"### {name}.md\n(Not found)")

        # LLM 分析
        prompt = f"""Analyze the following wiki pages for contradictions or conflicting statements.

{chr(10).join(contents)}

Return JSON:
{{
  "contradictions": [
    {{
      "description": "clear description of what conflicts",
      "pages": ["page1.md", "page2.md"],
      "severity": "high" or "medium" or "low"
    }}
  ]
}}
If no contradictions found, return {{"contradictions": []}}."""

        response = self.llm.chat_json([{"role": "user", "content": prompt}])
        return response.get("contradictions", [])

    def check_all_potential_conflicts(self) -> List[Dict]:
        """检查 Wiki 中所有潜在矛盾

        通过分析可能相互冲突的页面类型：
        - entity 页面之间的配置冲突
        - procedure 页面之间的步骤差异

        Returns:
            所有检测到的矛盾列表
        """
        from llm_wiki.link_graph import LinkGraph

        graph = LinkGraph(self.wiki)
        graph.load()

        contradictions = []

        # 检查 entity 页面之间的冲突
        entity_pages = [p for p in graph.get_all_pages() if p.startswith("entity-")]

        # 每次检查最多 5 个页面，避免 prompt 过长
        for i in range(0, len(entity_pages), 5):
            batch = entity_pages[i:i+5]
            batch_contradictions = self.check_pages(batch)
            contradictions.extend(batch_contradictions)

        # 检查 procedure 页面之间的冲突
        proc_pages = [p for p in graph.get_all_pages() if p.startswith("procedure-")]

        for i in range(0, len(proc_pages), 5):
            batch = proc_pages[i:i+5]
            batch_contradictions = self.check_pages(batch)
            contradictions.extend(batch_contradictions)

        return contradictions

    def mark_page(self, page_name: str, contradiction: Dict) -> None:
        """在页面添加矛盾标记

        Args:
            page_name: 页面名称
            contradiction: 矛盾信息，包含 description, pages, severity
        """
        content = self.wiki.read_wiki_page(page_name)

        # 生成标记
        severity = contradiction.get("severity", "medium").upper()
        related = ", ".join(contradiction.get("pages", []))
        description = contradiction.get("description", "")

        marker = f"""
> [!CONTRADICT] {severity}
> Related: {related}
> {description}

---

"""

        # 插入到 front-matter 之后
        from llm_wiki.frontmatter import FrontMatter
        fm = FrontMatter(content)
        body = content[len(fm._raw_front_matter):] if fm._raw_front_matter else content

        # 添加标记到开头
        new_content = fm._raw_front_matter + marker + body
        self.wiki.write_wiki_page(page_name, new_content)

    def find_and_mark_all(self) -> Dict[str, int]:
        """查找并标记所有矛盾

        Returns:
            统计信息 {found, marked, errors}
        """
        contradictions = self.check_all_potential_conflicts()

        found = len(contradictions)
        marked = 0
        errors = 0

        # 去重：每对页面只标记一次
        marked_pages = set()

        for contradiction in contradictions:
            pages = contradiction.get("pages", [])
            for page in pages:
                # 移除 .md 后缀
                if page.endswith(".md"):
                    page = page[:-3]

                if page not in marked_pages:
                    try:
                        self.mark_page(page, contradiction)
                        marked_pages.add(page)
                        marked += 1
                    except Exception as e:
                        print(f"Error marking {page}: {e}")
                        errors += 1

        return {
            "found": found,
            "marked": marked,
            "errors": errors,
        }

    def clear_markers(self, page_name: str) -> None:
        """清除页面中的矛盾标记"""
        content = self.wiki.read_wiki_page(page_name)

        # 移除所有矛盾标记
        pattern = r'> \[!CONTRADICT\].*?(?=---|\n\n|\Z)'
        new_content = re.sub(pattern, '', content, flags=re.DOTALL | re.MULTILINE)

        self.wiki.write_wiki_page(page_name, new_content)
