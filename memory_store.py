import hashlib
import json
import re
import threading
import time
from pathlib import Path
from typing import Any, Optional


class MemoryStore:
    def __init__(
        self,
        base_dir: str = "data/memory",
        max_recent_turns: int = 8,
        max_active_files: int = 3,
        max_relevant_chunks: int = 5,
        max_summary_chars: int = 6000,
    ):
        self.base_dir = Path(base_dir)
        self.max_recent_turns = max_recent_turns
        self.max_active_files = max_active_files
        self.max_relevant_chunks = max_relevant_chunks
        self.max_summary_chars = max_summary_chars
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self._user_locks: dict[str, threading.RLock] = {}
        self._user_locks_meta = threading.Lock()

    def _get_user_lock(self, user_id: str) -> threading.RLock:
        with self._user_locks_meta:
            if user_id not in self._user_locks:
                self._user_locks[user_id] = threading.RLock()
            return self._user_locks[user_id]

    def get(self, user_id: str) -> dict[str, Any]:
        with self._get_user_lock(user_id):
            path = self._path(user_id)
            if not path.exists():
                return self._empty()
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                data.setdefault("recent_turns", [])
                data.setdefault("dialogue_summary", "")
                data.setdefault("active_files", [])
                data.setdefault("llm_history", [])
                return data
            except Exception:
                return self._empty()

    def save(self, user_id: str, memory: dict[str, Any]) -> None:
        with self._get_user_lock(user_id):
            path = self._path(user_id)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(memory, ensure_ascii=False, indent=2), encoding="utf-8")

    def add_turn(self, user_id: str, user_message: str, assistant_reply: str, files: Optional[list[Any]] = None) -> None:
        with self._get_user_lock(user_id):
            memory = self.get(user_id)
            memory["recent_turns"].append({
                "user": user_message,
                "assistant": assistant_reply,
                "files": [self._file_turn_summary(file_ctx) for file_ctx in (files or [])],
                "created_at": int(time.time()),
            })
            if len(memory["recent_turns"]) > self.max_recent_turns:
                overflow = memory["recent_turns"][:-self.max_recent_turns]
                memory["dialogue_summary"] = self._append_summary(memory.get("dialogue_summary", ""), overflow)
                memory["recent_turns"] = memory["recent_turns"][-self.max_recent_turns:]
            memory["updated_at"] = int(time.time())
            self.save(user_id, memory)

    def add_active_file(self, user_id: str, file_ctx: Any, chunk_summaries: Optional[list[str]] = None) -> dict[str, Any]:
        with self._get_user_lock(user_id):
            memory = self.get(user_id)
            file_record = self._file_record(file_ctx, chunk_summaries or [])
            files = [item for item in memory.get("active_files", []) if item.get("file_id") != file_record["file_id"]]
            files.insert(0, file_record)
            memory["active_files"] = files[: self.max_active_files]
            memory["updated_at"] = int(time.time())
            self.save(user_id, memory)
            return file_record

    def build_context(self, user_id: str, user_message: str, include_active_file: bool = True) -> list[dict[str, str]]:
        with self._get_user_lock(user_id):
            memory = self.get(user_id)
            messages = []
            if memory.get("dialogue_summary"):
                messages.append({"role": "system", "content": f"此前对话摘要：{memory['dialogue_summary']}"})

            if include_active_file:
                file_context = self._active_file_prompt(memory, user_message)
                if file_context:
                    messages.append({"role": "system", "content": file_context})

            for turn in memory.get("recent_turns", [])[-self.max_recent_turns:]:
                messages.append({"role": "user", "content": turn.get("user", "")})
                messages.append({"role": "assistant", "content": turn.get("assistant", "")})
            return messages

    def _active_file_prompt(self, memory: dict[str, Any], user_message: str) -> str:
        active_files = memory.get("active_files", [])
        if not active_files:
            return ""

        active = active_files[0]
        chunks = self._select_chunks(active.get("chunk_summaries", []), user_message)
        lines = [
            "当前活跃文件上下文如下。用户后续提到“这个文件”“刚才的文档”“其中的数据”等，通常指这个活跃文件。",
            f"文件名：{active.get('filename', '')}",
            f"路径：{active.get('path', '')}",
            f"类型：{active.get('mime_type', '')}",
            f"估算 tokens：{active.get('estimated_tokens', 0):,}",
        ]
        if active.get("summary"):
            lines.extend(["整体摘要：", active["summary"]])
        if chunks:
            lines.append("相关分块摘要：")
            for chunk in chunks:
                lines.append(f"[分块 {chunk.get('chunk_id')}] {chunk.get('summary', '')}")
        return "\n".join(lines)

    def _select_chunks(self, chunks: list[dict[str, Any]], query: str) -> list[dict[str, Any]]:
        if not chunks:
            return []
        keywords = self._keywords(query)
        if not keywords:
            return chunks[: min(2, self.max_relevant_chunks)]

        scored = []
        for chunk in chunks:
            text = f"{chunk.get('summary', '')} {' '.join(chunk.get('keywords', []))}".lower()
            score = sum(1 for keyword in keywords if keyword in text)
            if score:
                scored.append((score, chunk))
        if not scored:
            return chunks[: min(2, self.max_relevant_chunks)]
        scored.sort(key=lambda item: item[0], reverse=True)
        return [chunk for _, chunk in scored[: self.max_relevant_chunks]]

    def _file_record(self, file_ctx: Any, chunk_summaries: list[str]) -> dict[str, Any]:
        path = getattr(file_ctx, "path", "")
        filename = getattr(file_ctx, "filename", "")
        content = getattr(file_ctx, "content", "")
        file_id = hashlib.sha256(f"{path}:{filename}".encode("utf-8")).hexdigest()[:16]
        return {
            "file_id": file_id,
            "filename": filename,
            "path": path,
            "mime_type": getattr(file_ctx, "mime_type", ""),
            "estimated_tokens": getattr(file_ctx, "estimated_tokens", 0),
            "summary": getattr(file_ctx, "summary", "") or content,
            "chunk_summaries": [
                {
                    "chunk_id": index,
                    "summary": summary,
                    "keywords": self._keywords(summary)[:12],
                }
                for index, summary in enumerate(chunk_summaries, start=1)
            ],
            "created_at": int(time.time()),
        }

    def _file_turn_summary(self, file_ctx: Any) -> dict[str, Any]:
        return {
            "filename": getattr(file_ctx, "filename", ""),
            "estimated_tokens": getattr(file_ctx, "estimated_tokens", 0),
        }

    def _append_summary(self, old_summary: str, turns: list[dict[str, Any]]) -> str:
        lines = [old_summary.strip()] if old_summary else []
        for turn in turns:
            file_text = ""
            files = turn.get("files", [])
            if files:
                file_text = " 文件：" + "；".join(item.get("filename", "") for item in files if item.get("filename"))
            lines.append(f"用户：{turn.get('user', '')}{file_text}\n助手：{turn.get('assistant', '')}")
        summary = "\n".join(line for line in lines if line).strip()
        if len(summary) <= self.max_summary_chars:
            return summary
        return summary[-self.max_summary_chars:]

    def _keywords(self, text: str) -> list[str]:
        words = []
        for item in re.findall(r"[a-zA-Z0-9_]{2,}|[\u4e00-\u9fff]{2,}", text.lower()):
            if item not in words:
                words.append(item)
            if re.fullmatch(r"[\u4e00-\u9fff]{3,}", item):
                for index in range(0, len(item) - 1):
                    pair = item[index:index + 2]
                    if pair not in words:
                        words.append(pair)
        return words[:40]

    def _path(self, user_id: str) -> Path:
        safe = re.sub(r"[^a-zA-Z0-9_.@-]+", "_", user_id or "unknown")
        digest = hashlib.sha256((user_id or "unknown").encode("utf-8")).hexdigest()[:10]
        return self.base_dir / f"{safe[:80]}_{digest}.json"

    def _empty(self) -> dict[str, Any]:
        return {
            "dialogue_summary": "",
            "recent_turns": [],
            "active_files": [],
            "llm_history": [],
            "updated_at": int(time.time()),
        }

    def get_llm_history(self, user_id: str) -> list[dict[str, str]]:
        with self._get_user_lock(user_id):
            memory = self.get(user_id)
            return memory.get("llm_history", [])

    def save_llm_history(self, user_id: str, history: list[dict[str, str]]) -> None:
        with self._get_user_lock(user_id):
            memory = self.get(user_id)
            memory["llm_history"] = history
            memory["updated_at"] = int(time.time())
            self.save(user_id, memory)
