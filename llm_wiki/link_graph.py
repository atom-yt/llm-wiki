"""链接图缓存

持久化的页面链接图，用于快速查找链接关系、孤立页面等。
"""
import json
from pathlib import Path
from typing import Dict, Set, List, Tuple


class LinkGraph:
    """持久化的页面链接图，避免 O(n²) 重复计算"""

    def __init__(self, wiki):
        self.wiki = wiki
        self.cache_file = wiki.root / ".link_graph.json"
        self._graph: Dict[str, Set[str]] = {}
        self._dirty = False
        self._loaded = False

    def load(self) -> None:
        """从磁盘加载缓存"""
        if self._loaded:
            return

        if self.cache_file.exists():
            try:
                data = json.loads(self.cache_file.read_text())
                # 转换 list 回 set
                self._graph = {
                    k: set(v) if isinstance(v, list) else v
                    for k, v in data.items()
                }
                self._loaded = True
                return
            except (json.JSONDecodeError, ValueError):
                pass

        # 缓存不存在或无效，重建图
        self.rebuild()

    def rebuild(self) -> None:
        """从所有页面重建图"""
        pages = self.wiki.list_wiki_pages()

        # 初始化图
        self._graph = {page: set() for page in pages}

        # 分析每个页面的链接
        for page in pages:
            try:
                links = self.wiki.find_links_in_page(page)
                for link in links:
                    # 如果目标页存在，添加链接
                    if link in self._graph:
                        self._graph[link].add(page)  # inbound
                        self._graph[page].add(link)   # outbound
            except FileNotFoundError:
                continue

        self._dirty = True
        self.save()
        self._loaded = True

    def save(self) -> None:
        """保存到磁盘"""
        if self._dirty:
            # 转换 set 为 list 以便 JSON 序列化
            serializable = {k: list(v) for k, v in self._graph.items()}
            self.cache_file.write_text(json.dumps(serializable, indent=2))
            self._dirty = False

    def get_inbound(self, page: str) -> Set[str]:
        """获取指向该页面的链接（谁链接到这个页面）"""
        self.load()
        return self._graph.get(page, set())

    def get_outbound(self, page: str) -> Set[str]:
        """获取该页面指向的链接（这个页面链接到哪里）"""
        self.load()
        return self._graph.get(page, set())

    def add_link(self, from_page: str, to_page: str) -> None:
        """添加新链接（用于增量更新）"""
        self.load()

        if from_page not in self._graph:
            self._graph[from_page] = set()
        if to_page not in self._graph:
            self._graph[to_page] = set()

        self._graph[to_page].add(from_page)   # inbound
        self._graph[from_page].add(to_page)   # outbound
        self._dirty = True

    def remove_page(self, page: str) -> None:
        """从图中移除页面（用于删除页面）"""
        self.load()

        if page in self._graph:
            del self._graph[page]

        # 从其他页面的链接中移除
        for p in self._graph:
            if page in self._graph[p]:
                self._graph[p].remove(page)

        self._dirty = True

    def find_orphans(self) -> List[str]:
        """查找孤立页面（无入站链接，除了 source-*）"""
        self.load()

        orphans = []
        for page, inbound in self._graph.items():
            # source 页面本身就被孤立（作为总结页面）
            # 如果不是 source 页面且无入站链接
            if not page.startswith("source-") and len(inbound) == 0:
                orphans.append(page)

        return sorted(orphans)

    def find_hubs(self, limit: int = 10) -> List[Tuple[str, int]]:
        """查找枢纽页面（出站链接最多）"""
        self.load()

        hubs = []
        for page, outbound in self._graph.items():
            hubs.append((page, len(outbound)))

        hubs.sort(key=lambda x: x[1], reverse=True)
        return hubs[:limit]

    def get_page_stats(self, page: str) -> Dict[str, int]:
        """获取页面的链接统计"""
        self.load()

        if page not in self._graph:
            return {"inbound": 0, "outbound": 0}

        return {
            "inbound": len(self.get_inbound(page)),
            "outbound": len(self.get_outbound(page)),
        }

    def get_all_pages(self) -> List[str]:
        """获取图中所有页面"""
        self.load()
        return list(self._graph.keys())

    def is_connected(self, page1: str, page2: str) -> bool:
        """检查两个页面是否直接连接"""
        self.load()

        return (
            page2 in self._graph.get(page1, set()) or
            page1 in self._graph.get(page2, set())
        )

    def find_shortest_path(
        self,
        start: str,
        end: str,
        max_depth: int = 5
    ) -> List[str]:
        """查找两个页面之间的最短路径（BFS）"""
        self.load()

        if start not in self._graph or end not in self._graph:
            return []

        if start == end:
            return [start]

        from collections import deque

        queue = deque([(start, [start])])
        visited = {start}

        while queue:
            (node, path) = queue.popleft()

            if len(path) > max_depth:
                continue

            for neighbor in self._graph.get(node, set()):
                if neighbor == end:
                    return path + [end]

                if neighbor not in visited:
                    visited.add(neighbor)
                    queue.append((neighbor, path + [neighbor]))

        return []
