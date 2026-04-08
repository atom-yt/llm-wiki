"""智能页面选择

为新源文档选择相关的现有 Wiki 页面作为上下文。
"""
import re
import math
from pathlib import Path
from typing import List, Tuple, Dict, Set, Optional
from collections import Counter

from llm_wiki.wiki import WikiManager


class PageSelector:
    """智能选择相关页面作为上下文"""

    def __init__(self, wiki: WikiManager):
        self.wiki = wiki
        self._page_index: Dict[str, dict] = {}
        self._build_page_index()

    def _build_page_index(self) -> None:
        """构建页面索引（用于快速查找）"""
        pages = self.wiki.list_wiki_pages()

        for page in pages:
            try:
                content = self.wiki.read_wiki_page(page)
                tokens = self._tokenize(content)

                self._page_index[page] = {
                    "tokens": tokens,
                    "freq": Counter(tokens),
                    "length": len(tokens),
                    "content": content[:2000],  # 保留部分内容用于匹配
                }
            except FileNotFoundError:
                continue

    def _tokenize(self, text: str) -> List[str]:
        """简单分词"""
        # 移除 front-matter
        if text.startswith("---"):
            end = text.find("---", 3)
            if end != -1:
                text = text[end + 3:]

        # 提取单词（支持中文字符）
        # 英文单词：字母开头
        english_words = re.findall(r'\b[a-zA-Z][a-zA-Z0-9_-]*\b', text.lower())
        # 中文字符
        chinese_chars = re.findall(r'[\u4e00-\u9fa5]+', text)

        words = english_words + chinese_chars

        # 过滤停用词和短词
        stopwords = {'the', 'a', 'an', 'is', 'are', 'was', 'were', 'be', 'been',
                     'being', 'have', 'has', 'had', 'do', 'does', 'did', 'will',
                     'would', 'could', 'should', 'may', 'might', 'must', 'shall',
                     'can', 'need', 'dare', 'ought', 'used', 'to', 'of', 'in',
                     'for', 'on', 'with', 'at', 'by', 'from', 'as', 'into',
                     'through', 'during', 'before', 'after', 'above', 'below',
                     'between', 'under', 'again', 'further', 'then', 'once',
                     'here', 'there', 'when', 'where', 'why', 'how', 'all',
                     'each', 'few', 'more', 'most', 'other', 'some', 'such',
                     'no', 'nor', 'not', 'only', 'own', 'same', 'so', 'than',
                     'too', 'very', 'just', 'and', 'but', 'if', 'or', 'because',
                     'until', 'while', 'although', 'though', 'after', 'before',
                     'when', 'whenever', 'if', 'unless', 'until', 'lest'}

        return [w for w in words if w not in stopwords and len(w) > 1]

    def _extract_entities(self, text: str) -> List[str]:
        """提取实体（简单版本：大写开头的词组）"""
        # 提取连续的大写开头的词
        entities = re.findall(r'\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b', text)
        return list(set(entities))

    def _extract_keywords(self, text: str) -> List[str]:
        """提取关键词（使用词频）"""
        tokens = self._tokenize(text)
        freq = Counter(tokens)
        # 返回词频最高的词
        return [word for word, _ in freq.most_common(20)]

    def select_for_ingest(
        self,
        source_content: str,
        max_pages: int = 10
    ) -> List[str]:
        """为新源文档选择相关页面

        Args:
            source_content: 源文档内容
            max_pages: 最大返回页面数

        Returns:
            相关页面名称列表
        """
        if not self._page_index:
            return []

        # 步骤 1: 提取源中的实体和关键词
        entities = self._extract_entities(source_content)
        keywords = self._extract_keywords(source_content)

        # 步骤 2: 查找包含这些实体/关键词的现有页面
        candidates: Set[str] = set()

        for entity in entities:
            entity_lower = entity.lower()
            for page, data in self._page_index.items():
                if entity_lower in data["content"].lower():
                    candidates.add(page)

        for keyword in keywords[:10]:
            for page, data in self._page_index.items():
                if keyword in data["freq"]:
                    candidates.add(page)

        if not candidates:
            return []

        # 步骤 3: 计算相关性分数
        source_tokens = self._tokenize(source_content)
        source_freq = Counter(source_tokens)

        scored_pages = []
        for page in candidates:
            score = self._compute_relevance_score(source_freq, page)
            scored_pages.append((page, score))

        # 步骤 4: 返回最高分的 N 个页面
        scored_pages.sort(key=lambda x: x[1], reverse=True)
        return [page for page, _ in scored_pages[:max_pages]]

    def _compute_relevance_score(
        self,
        source_freq: Counter,
        page_name: str
    ) -> float:
        """计算源文档与页面的相关性分数"""
        if page_name not in self._page_index:
            return 0.0

        page_data = self._page_index[page_name]
        score = 0.0

        for token, tf in source_freq.items():
            if token in page_data["freq"]:
                # 简化的相关性计算
                df = sum(1 for d in self._page_index.values() if token in d["freq"])
                idf = 1.0 / (df + 1)
                score += idf * page_data["freq"][token]

        return score

    def select_for_query(
        self,
        query: str,
        top_k: int = 10
    ) -> List[Tuple[str, float]]:
        """为查询选择相关页面

        Args:
            query: 用户查询
            top_k: 返回的页面数量

        Returns:
            (page_name, score) 列表
        """
        if not self._page_index:
            return []

        query_tokens = self._tokenize(query)
        if not query_tokens:
            return []

        scores = []
        n = len(self._page_index)

        # 计算平均文档长度
        total_length = sum(d["length"] for d in self._page_index.values())
        avg_len = total_length / n if n > 0 else 0

        for page, data in self._page_index.items():
            score = 0.0

            for token in query_tokens:
                if token in data["freq"]:
                    tf = data["freq"][token]
                    df = sum(1 for d in self._page_index.values() if token in d["freq"])

                    # BM25 公式
                    k1 = 1.5
                    b = 0.75

                    idf = math.log((n - df + 0.5) / (df + 0.5) + 1)
                    numerator = tf * (k1 + 1)
                    denominator = tf + k1 * (1 - b + b * data["length"] / avg_len)

                    score += idf * (numerator / denominator)

            if score > 0:
                scores.append((page, score))

        scores.sort(key=lambda x: x[1], reverse=True)
        return scores[:top_k]
