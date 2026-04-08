"""QMD 语义检索集成

支持 QMD (Query Markdown) 本地语义检索，带 SimpleEmbedder 和 BM25 回退。
"""
import json
import math
import hashlib
import subprocess
from pathlib import Path
from typing import List, Tuple, Optional
from collections import Counter

from llm_wiki.wiki import WikiManager


class QMDEmbeddingCache:
    """嵌入向量缓存，避免重复计算"""

    def __init__(self, cache_dir: Path):
        self.cache_dir = cache_dir
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.index_file = self.cache_dir / "qmd_index.json"
        self._index = {}

    def load(self) -> bool:
        """加载缓存索引"""
        if self.index_file.exists():
            try:
                self._index = json.loads(self.index_file.read_text())
                return True
            except (json.JSONDecodeError, ValueError):
                pass
        return False

    def save(self) -> None:
        """保存缓存索引"""
        self.index_file.write_text(json.dumps(self._index, indent=2))

    def get(self, page: str) -> Optional[dict]:
        """获取页面的嵌入数据"""
        return self._index.get(page)

    def set(self, page: str, content_hash: str, embedding: list) -> None:
        """设置页面的嵌入数据"""
        self._index[page] = {
            "content_hash": content_hash,
            "embedding": embedding
        }

    def is_outdated(self, page: str, current_hash: str) -> bool:
        """检查页面内容是否已更新"""
        data = self._index.get(page)
        return data is None or data["content_hash"] != current_hash


class BM25Fallback:
    """当 QMD 不可用时的 BM25 回退策略"""

    def __init__(self, wiki: WikiManager):
        self.wiki = wiki
        self._index: dict = {}
        self._avg_doc_length = 0
        self.build_index()

    def build_index(self) -> None:
        """构建 BM25 倒排索引"""
        pages = self.wiki.list_wiki_pages()
        total_length = 0

        for page in pages:
            try:
                content = self.wiki.read_wiki_page(page)
                tokens = self._tokenize(content)
                freq = Counter(tokens)

                self._index[page] = {
                    "tokens": tokens,
                    "freq": freq,
                    "length": len(tokens)
                }
                total_length += len(tokens)
            except FileNotFoundError:
                continue

        self._avg_doc_length = total_length / len(pages) if pages else 0

    def _tokenize(self, text: str) -> List[str]:
        """简单分词"""
        import re

        # 移除 front-matter
        if text.startswith("---"):
            end = text.find("---", 3)
            if end != -1:
                text = text[end + 3:]

        # 提取单词
        words = re.findall(r'\b[a-zA-Z0-9_-]+\b', text.lower())
        return [w for w in words if len(w) > 2]

    def search(self, query: str, top_k: int = 10) -> List[str]:
        """BM25 搜索"""
        query_tokens = self._tokenize(query)
        if not query_tokens:
            return []

        k1 = 1.5  # term frequency saturation
        b = 0.75  # length normalization

        scores = []
        for page, doc in self._index.items():
            score = 0.0
            for token in query_tokens:
                if token in doc["freq"]:
                    tf = doc["freq"][token]
                    df = sum(1 for d in self._index.values() if token in d["freq"])
                    n = len(self._index)

                    idf = math.log((n - df + 0.5) / (df + 0.5) + 1)

                    # BM25 公式
                    numerator = tf * (k1 + 1)
                    denominator = tf + k1 * (1 - b + b * doc["length"] / self._avg_doc_length)
                    score += idf * (numerator / denominator)

            if score > 0:
                scores.append((page, score))

        scores.sort(key=lambda x: x[1], reverse=True)
        return [p for p, _ in scores[:top_k]]


class QMDRetriever:
    """QMD 语义检索器（带 SimpleEmbedder 和 BM25 回退）"""

    def __init__(self, wiki: WikiManager, enable_qmd: bool = True,
                 cache_dir: Optional[Path] = None):
        from llm_wiki.simple_embedder import SimpleEmbedder

        self.wiki = wiki
        self.enable_qmd = enable_qmd
        self.cache_dir = cache_dir or (wiki.root / ".qmd_cache")
        self.cache = QMDEmbeddingCache(self.cache_dir)
        self.fallback = BM25Fallback(wiki)

        # 初始化 SimpleEmbedder 作为中间层
        self.simple_embedder = SimpleEmbedder(wiki)

        # 尝试加载缓存
        self.cache.load()

    def search(self, query: str, top_k: int = 10) -> List[Tuple[str, float]]:
        """
        语义搜索，返回 (page_name, score) 列表

        优先使用 QMD，不可用时使用 SimpleEmbedder，最后回退到 BM25
        """
        # 优先级 1: QMD CLI 语义搜索
        if self.enable_qmd and self.is_available():
            try:
                return self._semantic_search(query, top_k)
            except Exception:
                # 静默失败，尝试下一个选项
                pass

        # 优先级 2: SimpleEmbedder 本地语义搜索
        # 检查是否有已索引的页面
        if len(self.simple_embedder._embeddings) > 0:
            try:
                return self.simple_embedder.search(query, top_k)
            except Exception:
                pass

        # 优先级 3: BM25 关键词搜索
        pages = self.fallback.search(query, top_k)
        return [(p, 1.0) for p in pages]

    def _semantic_search(self, query: str, top_k: int) -> List[Tuple[str, float]]:
        """使用 QMD 进行语义搜索"""
        # 通过 CLI 调用 QMD
        try:
            result = subprocess.run(
                ['qmd', 'search', query, '--top', str(top_k),
                 '--data', str(self.wiki.wiki_dir)],
                capture_output=True, text=True, timeout=30
            )

            if result.returncode == 0:
                # 解析 QMD 输出
                # 假设输出格式: page1.md:score1,page2.md:score2,...
                results = []
                for line in result.stdout.strip().split('\n'):
                    if ':' in line:
                        parts = line.rsplit(':', 1)
                        if len(parts) == 2:
                            page, score = parts
                            page = page.replace('.md', '')
                            try:
                                score_val = float(score)
                                results.append((page, score_val))
                            except ValueError:
                                results.append((page, 1.0))
                return results[:top_k]
        except (subprocess.TimeoutExpired, FileNotFoundError, subprocess.SubprocessError):
            pass

        # QMD 不可用，回退到 BM25
        pages = self.fallback.search(query, top_k)
        return [(p.replace('.md', ''), 1.0) for p in pages]

    def index_pages(self, force: bool = False) -> int:
        """
        对所有 wiki 页面建立嵌入索引

        优先使用 QMD CLI，不可用时使用 SimpleEmbedder
        """
        # 优先级 1: QMD CLI
        if self.is_available():
            return self._index_with_qmd(force)

        # 优先级 2: SimpleEmbedder 本地嵌入
        return self.simple_embedder.index_pages(force)

    def _index_with_qmd(self, force: bool = False) -> int:
        """使用 QMD CLI 建立索引"""
        pages = self.wiki.list_wiki_pages()
        indexed = 0

        for page in pages:
            try:
                content = self.wiki.read_wiki_page(page)
                content_hash = hashlib.md5(content.encode()).hexdigest()

                if force or self.cache.is_outdated(page, content_hash):
                    # 调用 QMD 生成嵌入
                    try:
                        result = subprocess.run(
                            ['qmd', 'embed',
                             '--input', str(self.wiki.wiki_dir / f"{page}.md")],
                            capture_output=True, text=True, timeout=30
                        )

                        if result.returncode == 0:
                            # 解析嵌入向量（假设是 JSON 格式）
                            try:
                                embedding_data = json.loads(result.stdout)
                                embedding = embedding_data.get("embedding", [])
                                self.cache.set(page, content_hash, embedding)
                                indexed += 1
                            except (json.JSONDecodeError, ValueError):
                                pass
                    except (subprocess.TimeoutExpired, FileNotFoundError,
                            subprocess.SubprocessError):
                        # 静默失败
                        pass
            except Exception:
                # 静默失败
                pass

        if indexed > 0:
            self.cache.save()

        return indexed

    def is_available(self) -> bool:
        """检查 QMD 是否可用"""
        if not self.enable_qmd:
            return False

        # 检查 QMD 是否安装
        try:
            result = subprocess.run(['qmd', '--version'],
                                   capture_output=True, timeout=5)
            return result.returncode == 0
        except (subprocess.TimeoutExpired, FileNotFoundError, subprocess.SubprocessError):
            return False

    def rebuild_index(self) -> int:
        """强制重建索引"""
        return self.index_pages(force=True)

    def get_status(self) -> dict:
        """获取检索器状态"""
        return {
            "available": self.is_available(),
            "cache_dir": str(self.cache_dir),
            "cache_exists": self.cache.index_file.exists(),
            "indexed_pages": len(self.simple_embedder._embeddings) if len(self.simple_embedder._embeddings) > 0 else len(self.cache._index),
            "total_pages": len(self.wiki.list_wiki_pages()),
            "search_mode": self._get_search_mode(),
        }

    def _get_search_mode(self) -> str:
        """获取当前搜索模式"""
        if self.is_available():
            return "QMD Semantic"
        elif len(self.simple_embedder._embeddings) > 0:
            return "SimpleEmbedder (TF-IDF)"
        else:
            return "BM25 Keyword"
