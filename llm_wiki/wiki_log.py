"""可解析的 Wiki 操作日志

同时维护 Markdown（人类可读）和 JSON（机器可读）两种格式。
"""
import json
from datetime import datetime
from typing import Optional, Dict, List
import uuid
from pathlib import Path


class WikiLog:
    """可解析的 Wiki 操作日志"""

    def __init__(self, wiki):
        """
        Args:
            wiki: WikiManager 实例
        """
        self.wiki = wiki
        self.log_file = wiki.wiki_dir / "log.md"
        self._json_file = wiki.wiki_dir / "log.json"

    def append_entry(
        self,
        action: str,
        title: str,
        details: List[str],
        pages_affected: List[str] = None,
        metadata: Dict = None
    ) -> str:
        """添加日志条目

        Args:
            action: 操作类型 (ingest, query, lint, etc.)
            title: 标题
            details: 详细信息列表
            pages_affected: 影响的页面列表
            metadata: 额外元数据

        Returns:
            entry_id: 日志条目 ID
        """
        entry_id = str(uuid.uuid4())[:8]
        timestamp = datetime.now().isoformat()

        entry = {
            "id": entry_id,
            "timestamp": timestamp,
            "action": action,
            "title": title,
            "details": details,
            "pages_affected": pages_affected or [],
            "metadata": metadata or {}
        }

        # JSON 格式（机器可读）
        self._append_json_entry(entry)

        # Markdown 格式（人类可读）
        self._append_markdown_entry(entry)

        return entry_id

    def _append_json_entry(self, entry: Dict) -> None:
        """追加到 JSON 日志"""
        entries = []
        if self._json_file.exists():
            try:
                entries = json.loads(self._json_file.read_text())
                if not isinstance(entries, list):
                    entries = []
            except (json.JSONDecodeError, ValueError):
                entries = []
        entries.append(entry)
        self._json_file.write_text(json.dumps(entries, indent=2, ensure_ascii=False))

    def _append_markdown_entry(self, entry: Dict) -> None:
        """追加到 Markdown 日志"""
        date_str = datetime.fromisoformat(entry["timestamp"]).strftime("%Y-%m-%d %H:%M")
        markdown = f"""

## [{date_str}] {entry['action']} | {entry['title']}
> **Entry ID:** `{entry['id']}`
"""
        for detail in entry["details"]:
            markdown += f"\n- {detail}"

        if entry["pages_affected"]:
            # 将页面列表转为链接
            links = [f"[{p}]({p})" for p in entry["pages_affected"]]
            markdown += f"\n\n**Affected pages:** {', '.join(links)}"

        with open(self.log_file, "a", encoding="utf-8") as f:
            f.write(markdown)

    def get_recent(self, n: int = 10) -> List[Dict]:
        """获取最近的 n 条日志

        Args:
            n: 返回的条目数量

        Returns:
            日志条目列表（按时间倒序）
        """
        if not self._json_file.exists():
            return []
        try:
            entries = json.loads(self._json_file.read_text())
            return entries[-n:] if isinstance(entries, list) else []
        except (json.JSONDecodeError, ValueError):
            return []

    def get_by_id(self, entry_id: str) -> Optional[Dict]:
        """根据 ID 获取条目

        Args:
            entry_id: 日志条目 ID

        Returns:
            日志条目或 None
        """
        if not self._json_file.exists():
            return None
        try:
            entries = json.loads(self._json_file.read_text())
            for entry in entries:
                if entry.get("id") == entry_id:
                    return entry
        except (json.JSONDecodeError, ValueError):
            pass
        return None

    def get_entries_for_page(self, page_name: str) -> List[Dict]:
        """获取影响特定页面的所有日志

        Args:
            page_name: 页面名称

        Returns:
            相关日志条目列表
        """
        if not self._json_file.exists():
            return []
        try:
            entries = json.loads(self._json_file.read_text())
            return [
                e for e in entries
                if page_name in e.get("pages_affected", [])
            ]
        except (json.JSONDecodeError, ValueError):
            return []

    def get_entries_by_action(self, action: str) -> List[Dict]:
        """获取特定操作类型的所有日志

        Args:
            action: 操作类型

        Returns:
            相关日志条目列表
        """
        if not self._json_file.exists():
            return []
        try:
            entries = json.loads(self._json_file.read_text())
            return [e for e in entries if e.get("action") == action]
        except (json.JSONDecodeError, ValueError):
            return []

    def search(self, query: str) -> List[Dict]:
        """搜索日志

        Args:
            query: 搜索关键词

        Returns:
            匹配的日志条目列表
        """
        if not self._json_file.exists():
            return []
        try:
            entries = json.loads(self._json_file.read_text())
            results = []
            query_lower = query.lower()
            for entry in entries:
                # 搜索标题、详情和元数据
                if query_lower in entry.get("title", "").lower():
                    results.append(entry)
                    continue
                for detail in entry.get("details", []):
                    if query_lower in detail.lower():
                        results.append(entry)
                        break
            return results
        except (json.JSONDecodeError, ValueError):
            return []

    def get_stats(self) -> Dict:
        """获取日志统计信息

        Returns:
            统计信息字典
        """
        if not self._json_file.exists():
            return {"total": 0, "by_action": {}}

        try:
            entries = json.loads(self._json_file.read_text())
            by_action = {}
            for entry in entries:
                action = entry.get("action", "unknown")
                by_action[action] = by_action.get(action, 0) + 1

            return {
                "total": len(entries),
                "by_action": by_action
            }
        except (json.JSONDecodeError, ValueError):
            return {"total": 0, "by_action": {}}

    def export_markdown(self, output_path: Path = None) -> str:
        """导出完整的 Markdown 日志

        Args:
            output_path: 输出路径（可选）

        Returns:
            Markdown 内容
        """
        if not self._json_file.exists():
            return "# Wiki Log\n\nNo entries."

        try:
            entries = json.loads(self._json_file.read_text())

            md = "# Wiki Log\n\n"
            for entry in entries:
                date_str = datetime.fromisoformat(
                    entry["timestamp"]
                ).strftime("%Y-%m-%d %H:%M")

                md += f"## [{date_str}] {entry['action']} | {entry['title']}\n"
                md += f"> **Entry ID:** `{entry['id']}`\n\n"

                for detail in entry.get("details", []):
                    md += f"- {detail}\n"

                if entry.get("pages_affected"):
                    links = [f"[{p}]({p})" for p in entry["pages_affected"]]
                    md += f"\n**Affected pages:** {', '.join(links)}\n"

                md += "\n---\n"

            if output_path:
                output_path.write_text(md)

            return md
        except (json.JSONDecodeError, ValueError):
            return "# Wiki Log\n\nError reading log."
