"""简单的嵌入模块

使用本地 LLM 生成文档嵌入，作为 QMD 的替代方案。
"""
import hashlib
import json
from pathlib import Path
from typing import List, Tuple, Optional
import math

from llm_wiki.wiki import WikiManager


class SimpleEmbedder:
    """简单的文档嵌入器"""

    def __init__(self, wiki: WikiManager):
        self.wiki = wiki
        self._cache_file = wiki.root / ".embeddings.json"
        self._embeddings = {}
        self._load()

    def _load(self) -> None:
        """从缓存加载嵌入"""
        if self._cache_file.exists():
            try:
                with open(self._cache_file, 'r', encoding='utf-8') as f:
                    self._embeddings = json.load(f)
            except (json.JSONDecodeError, ValueError):
                pass

    def _save(self) -> None:
        """保存嵌入到缓存"""
        with open(self._cache_file, 'w', encoding='utf-8') as f:
            json.dump(self._embeddings, f, indent=2)

    def _get_text_chunks(self, text: str, max_tokens: int = 512) -> List[str]:
        """将文本分成小块

        Args:
            text: 输入文本
            max_tokens: 每块的最大 token 数

        Returns:
            文本块列表
        """
        # 简单的按段落分块
        paragraphs = [p.strip() for p in text.split('\n\n') if p.strip()]
        chunks = []
        current_chunk = []
        current_tokens = 0

        for para in paragraphs:
            # 粗略估算 token 数（英文约 4 字符 = 1 token）
            para_tokens = len(para) // 4

            if current_tokens + para_tokens > max_tokens:
                chunks.append('\n'.join(current_chunk))
                current_chunk = []
                current_tokens = 0

            current_chunk.append(para)
            current_tokens += para_tokens

        if current_chunk:
            chunks.append('\n'.join(current_chunk))

        return chunks

    def _generate_embedding(self, text: str) -> List[float]:
        """
        生成简单的文本嵌入

        这是一个简化版，使用词频和位置编码生成 768 维向量
        不是真正的 embedding，但可以用于基本的语义相似度计算
        """
        # 简化：使用词频向量
        from collections import Counter

        words = text.lower().split()
        # 过滤停用词
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
                     'until', 'while', 'although', 'though', 'yet', 'still',
                     'this', 'that', 'it', 'which', 'what', 'where'}

        word_counts = Counter([w for w in words if w not in stopwords and len(w) > 2])
        total_words = sum(word_counts.values())

        # 生成 768 维向量（使用词频）
        # 取前 768 个最常见词作为维度
        top_words = [w for w, _ in word_counts.most_common(768)]
        word_to_idx = {w: i for i, w in enumerate(top_words)}

        embedding = [0.0] * 768
        for word, count in word_counts.items():
            if word in word_to_idx:
                # 使用 TF-IDF 风格
                idx = word_to_idx[word]
                # 简化的 IDF（不是真实的）
                idf = math.log(1 + (total_words / (count + 1)))

                # 归一化的词频
                normalized_count = count / max(word_counts.values())
                embedding[idx] = normalized_count * idf

        return embedding

    def embed_page(self, page_name: str) -> Optional[List[float]]:
        """为页面生成嵌入

        Args:
            page_name: 页面名称

        Returns:
            嵌入向量或 None
        """
        # 检查缓存
        if page_name in self._embeddings:
            return self._embeddings[page_name]

        # 读取页面内容
        try:
            content = self.wiki.read_wiki_page(page_name)
        except FileNotFoundError:
            return None

        # 移除 front-matter
        if content.startswith('---'):
            end = content.find('---', 3)
            if end != -1:
                content = content[end + 3:]

        # 生成嵌入
        embedding = self._generate_embedding(content)
        self._embeddings[page_name] = embedding

        # 定期保存
        self._save()

        return embedding

    def search(self, query: str, top_k: int = 10) -> List[Tuple[str, float]]:
        """
        使用余弦相似度搜索最相关的页面

        Args:
            query: 查询文本
            top_k: 返回的页面数量

        Returns:
            (page_name, similarity) 列表
        """
        query_embedding = self._generate_embedding(query)

        scores = []
        for page_name, embedding in self._embeddings.items():
            # 计算余弦相似度
            dot_product = sum(a * b for a, b in zip(query_embedding, embedding))

            norm_query = math.sqrt(sum(x * x for x in query_embedding))
            norm_page = math.sqrt(sum(x * x for x in embedding))

            if norm_query == 0 or norm_page == 0:
                similarity = 0.0
            else:
                similarity = dot_product / (norm_query * norm_page)

            scores.append((page_name, similarity))

        # 按相似度排序
        scores.sort(key=lambda x: x[1], reverse=True)
        return scores[:top_k]

    def index_pages(self, force: bool = False) -> int:
        """为所有页面建立嵌入索引

        Args:
            force: 是否强制重建索引

        Returns:
            索引的页面数量
        """
        pages = self.wiki.list_wiki_pages()

        if not pages:
            return 0

        indexed = 0
        if force:
            self._embeddings = {}

        for page in pages:
            if force or page not in self._embeddings:
                if self.embed_page(page):
                    indexed += 1

        self._save()

        return indexed

    def get_status(self) -> dict:
        """获取索引状态"""
        return {
            "available": True,  # 简单嵌入器总是可用
            "cache_file": str(self._cache_file),
            "cache_exists": self._cache_file.exists(),
            "indexed_pages": len(self._embeddings),
            "total_pages": len(self.wiki.list_wiki_pages()),
        }
