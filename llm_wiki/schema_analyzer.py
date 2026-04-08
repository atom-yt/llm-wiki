"""Schema 分析和建议

分析 Wiki 结构并建议 Schema 改进。
"""
from typing import List, Dict, Optional
from collections import Counter


def analyze_and_suggest(wiki, llm) -> List[Dict]:
    """分析 Wiki 结构并建议 Schema 改进

    Args:
        wiki: WikiManager 实例
        llm: LLMClient 实例

    Returns:
        建议列表，每个建议包含 priority, title, description, code
    """
    # 收集信息
    page_types = _get_page_type_distribution(wiki)
    missing_pages = _find_missing_references(wiki)
    orphan_pages = _find_orphan_pages(wiki)
    unused_types = _find_unused_page_types(wiki, page_types)
    link_stats = _get_link_statistics(wiki)

    # 构建 prompt
    prompt = f"""Analyze this wiki structure and suggest improvements.

## Current Schema
{wiki.read_schema()}

## Page Type Distribution
{page_types}

## Issues Found
- Missing references: {missing_pages}
- Orphan pages (no inbound links): {orphan_pages}
- Unused page types: {unused_types}

## Link Statistics
{link_stats}

## Instructions
Analyze the above data and suggest improvements to:
1. Better organize the wiki structure
2. Improve page naming conventions
3. Add missing cross-references
4. Address orphan pages
5. Fix broken links
6. Suggest new page types if needed

Return JSON:
{{
  "suggestions": [
    {{
      "priority": "high" or "medium" or "low",
      "title": "suggestion title",
      "description": "why this change is needed",
      "code": "optional code snippet or example"
    }}
  ]
}}
If no improvements needed, return {{"suggestions": []}}."""

    try:
        response = llm.chat_json([{"role": "user", "content": prompt}])
        return response.get("suggestions", [])
    except Exception as e:
        # LLM 调用失败，返回基础分析
        return _generate_basic_suggestions(
            orphan_pages, missing_pages, unused_types, page_types
        )


def _get_page_type_distribution(wiki) -> str:
    """获取页面类型分布"""
    from collections import Counter

    pages = wiki.list_wiki_pages()
    type_counter = Counter()

    for page in pages:
        page_type = _infer_page_type(page)
        type_counter[page_type] += 1

    result = "Page Type Distribution:\n"
    for page_type, count in sorted(type_counter.items()):
        result += f"- {page_type}: {count}\n"

    return result


def _find_missing_references(wiki) -> List[str]:
    """查找缺失的引用（链接到不存在的页面）"""
    missing = []

    for page in wiki.list_wiki_pages():
        try:
            links = wiki.find_links_in_page(page)
            for link in links:
                if link not in ("index", "log") and not wiki.wiki_page_exists(link):
                    missing.append(link)
        except FileNotFoundError:
            continue

    return list(set(missing))[:20]


def _find_orphan_pages(wiki) -> List[str]:
    """查找孤立页面（无入站链接）"""
    from llm_wiki.link_graph import LinkGraph

    graph = LinkGraph(wiki)
    try:
        graph.load()
    except:
        graph.rebuild()

    return graph.find_orphans()


def _find_unused_page_types(wiki, type_distribution: str) -> List[str]:
    """查找未使用的页面类型"""
    # 解析类型分布
    types = []
    for line in type_distribution.split('\n'):
        if line.strip().startswith('-'):
            parts = line.split(':')
            if len(parts) == 2:
                types.append(parts[0].strip('- '))

    # Schema 中定义的类型
    schema_text = wiki.read_schema()
    defined_types = []
    for line in schema_text.split('\n'):
        if '##' in line and 'Page Types' not in line:
            continue
        if '-' in line and 'type' in schema_text:
            type_name = line.strip('- ')
            if type_name:
                defined_types.append(type_name)

    # 找出未使用的
    return [t for t in defined_types if t not in types]


def _get_link_statistics(wiki) -> str:
    """获取链接统计"""
    from llm_wiki.link_graph import LinkGraph

    graph = LinkGraph(wiki)
    try:
        graph.load()
    except:
        graph.rebuild()

    total_pages = len(graph.get_all_pages())
    if total_pages == 0:
        return "No pages found."

    hubs = graph.find_hubs(limit=5)
    orphans = graph.find_orphans()

    result = f"Link Statistics:\n"
    result += f"- Total pages: {total_pages}\n"
    result += f"- Orphan pages: {len(orphans)}\n"
    result += f"\nTop linked pages (hubs):\n"
    for page, count in hubs:
        result += f"  - {page}: {count} links\n"

    return result


def _infer_page_type(filename: str) -> str:
    """从文件名推断页面类型"""
    if filename.startswith("source-"):
        return "source"
    elif filename.startswith("entity-"):
        return "entity"
    elif filename.startswith("concept-"):
        return "concept"
    elif filename.startswith("procedure-"):
        return "procedure"
    elif filename.startswith("incident-"):
        return "incident"
    elif filename.startswith("query-"):
        return "query"
    return "other"


def _generate_basic_suggestions(
    orphan_pages: List[str],
    missing_pages: List[str],
    unused_types: List[str],
    type_distribution: str
) -> List[Dict]:
    """生成基础建议（当 LLM 不可用时）"""
    suggestions = []

    if orphan_pages:
        suggestions.append({
            "priority": "high" if len(orphan_pages) < 5 else "medium",
            "title": f"{len(orphan_pages)} orphan pages found",
            "description": "These pages have no inbound links and may be difficult to discover.",
            "code": f"Orphan pages: {', '.join(orphan_pages[:10])}"
        })

    if missing_pages:
        suggestions.append({
            "priority": "high",
            "title": f"{len(missing_pages)} broken links",
            "description": "Links to non-existent pages should be fixed or created.",
            "code": f"Missing: {', '.join(missing_pages[:10])}"
        })

    if unused_types:
        suggestions.append({
            "priority": "low",
            "title": f"Unused page types: {', '.join(unused_types)}",
            "description": "Consider using these page types or removing them from the schema.",
            "code": ""
        })

    return suggestions


def suggest_page_name(wiki, llm, title: str, page_type: str) -> str:
    """为新页面建议文件名

    Args:
        wiki: WikiManager 实例
        llm: LLMClient 实例
        title: 页面标题
        page_type: 页面类型 (source, entity, concept, procedure)

    Returns:
        建议的文件名（不含 .md）
    """
    prompt = f"""Given this page information, generate a suitable filename.

Page Type: {page_type}
Page Title: {title}

Rules:
- Use kebab-case (lowercase with hyphens)
- Start with the page type prefix (e.g., entity-, concept-, procedure-)
- Keep the filename under 60 characters
- Make it descriptive but concise

Return JSON: {{"filename": "page-name"}}"""

    try:
        response = llm.chat_json([{"role": "user", "content": prompt}])
        filename = response.get("filename", "")
        if not filename.startswith(f"{page_type}-"):
            filename = f"{page_type}-{filename}"
        return filename[:60]
    except Exception:
        # 回退到 slugify
        import re
        slug = title.lower().strip()
        slug = re.sub(r"[^\w\s-]", "", slug)
        slug = re.sub(r"[\s_]+", "-", slug)
        slug = slug.strip("-")[:50]
        return f"{page_type}-{slug}"
