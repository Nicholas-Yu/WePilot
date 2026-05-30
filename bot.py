import hashlib
import json
import logging
import os
import re
import signal
import sys
import time
from collections import OrderedDict
from pathlib import Path
from typing import Optional

from document_analyzer import DocumentAnalyzer, FileContext
from file_service import AttachmentStore
from ilink_client import ILinkClient
from llm_engine import LLMEngine
from memory_store import MemoryStore
from message_parser import MessageParser
from skill_runtime import SkillRuntime
import replies


def _load_dotenv(path: str = ".env"):
    env_path = Path(path)
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip("\"'")
        if key and key not in os.environ:
            os.environ[key] = value

PID_FILE = Path("data/bot.pid")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("bot")


def check_single_instance():
    """检查是否已有实例在运行"""
    PID_FILE.parent.mkdir(parents=True, exist_ok=True)
    
    # 检查 PID 文件是否存在
    if PID_FILE.exists():
        try:
            with open(PID_FILE, 'r') as f:
                old_pid = int(f.read().strip())
            
            # 检查进程是否存在
            try:
                os.kill(old_pid, 0)  # 信号0不发送任何信号，但会检查进程是否存在
                logger.error(f"机器人已在运行中 (PID: {old_pid})，请先停止旧进程")
                logger.info(f"停止命令: kill {old_pid}")
                return False
            except OSError:
                logger.info(f"发现旧的 PID 文件，但进程 {old_pid} 已不存在，将清理并启动")
                PID_FILE.unlink()
        except (ValueError, IOError) as e:
            logger.warning(f"读取 PID 文件失败: {e}，将重新创建")
            PID_FILE.unlink()
    
    # 创建 PID 文件并加锁
    try:
        PID_FILE.write_text(str(os.getpid()))
        logger.info(f"进程锁已创建 (PID: {os.getpid()})")
        return True
    except Exception as e:
        logger.error(f"创建 PID 文件失败: {e}")
        return False


def cleanup_pid_file():
    """清理 PID 文件"""
    try:
        if PID_FILE.exists():
            PID_FILE.unlink()
            logger.info("PID 文件已清理")
    except Exception as e:
        logger.warning(f"清理 PID 文件失败: {e}")


class WeChatBot:
    def __init__(self):
        self.config = self._load_config()
        self.ilink = ILinkClient()
        self.parser = MessageParser()
        file_cfg = self.config.get("files", {})
        max_upload_mb = file_cfg.get("max_upload_mb", 200)
        context_tokens = self.config.get("llm", {}).get("context_window_tokens", 1000000)
        reserved_tokens = file_cfg.get("reserved_prompt_tokens", 150000)
        max_file_tokens = file_cfg.get("max_file_tokens", max(1000, context_tokens - reserved_tokens))
        self.attachments = AttachmentStore(
            max_file_bytes=max_upload_mb * 1024 * 1024,
            retention_days=file_cfg.get("upload_retention_days", 30),
        )
        self.documents = DocumentAnalyzer(
            max_file_tokens=max_file_tokens,
            multimodal=self.config.get("multimodal", {}),
        )
        self.max_total_file_tokens = file_cfg.get("max_total_file_tokens", max_file_tokens)
        self.large_file_strategy = file_cfg.get("large_file_strategy", "chunk_summary")
        memory_cfg = self.config.get("memory", {})
        self.memory = MemoryStore(
            base_dir=memory_cfg.get("base_dir", "data/memory"),
            max_recent_turns=memory_cfg.get("max_recent_turns", 8),
            max_active_files=memory_cfg.get("max_active_files", 3),
            max_relevant_chunks=memory_cfg.get("max_relevant_chunks", 5),
            max_summary_chars=memory_cfg.get("max_summary_chars", 6000),
        )
        self.llm = LLMEngine(memory_store=self.memory)
        skill_cfg = self.config.get("skills", {})
        self.skills = SkillRuntime(
            skill_dirs=skill_cfg.get("dirs", ["skills", "user_skills"]),
            max_loaded_skills=skill_cfg.get("max_loaded_skills", 2),
        )
        self.debug_dir = Path("data/debug_messages")
        self._running = False
        self._seen_msgs: OrderedDict[str, float] = OrderedDict()
        self._seen_msgs_ttl = 300
        self._seen_msgs_max = 500
        reply_cfg = self.config.get("reply", {})
        self.max_chat_chars = reply_cfg.get("max_chat_chars", 800)
        self.auto_split_threshold = reply_cfg.get("auto_split_threshold", 2000)
        self.file_output_threshold = reply_cfg.get("file_output_threshold", 3000)
        self.split_delay = reply_cfg.get("split_delay_seconds", 0.5)
        self._pending_file_reports: dict[str, dict] = {}
        self._last_cleanup = 0.0

    def _load_config(self) -> dict:
        path = Path("config.json")
        if not path.exists():
            return {}
        return json.loads(path.read_text(encoding="utf-8"))

    def _handle_signal(self, sig, frame):
        logger.info("shutting down...")
        self._running = False
        cleanup_pid_file()
        try:
            self.ilink.notify_stop()
        except Exception:
            pass
        sys.exit(0)

    def _check_dangerous_command(self, text: str) -> Optional[str]:
        if not text:
            return None
        
        text_lower = text.lower().strip()
        
        dangerous_patterns = [
            (r'\b(rm|del|delete|remove|清除|删除|清空|抹除)\b', replies.DANGEROUS_COMMAND_BLOCKED),
            (r'\b(drop|truncate|alter\s+table)\b', replies.DANGEROUS_COMMAND_BLOCKED),
            (r'\b(kill|pkill|killall|终止|杀死)\b', replies.DANGEROUS_COMMAND_BLOCKED),
            (r'\b(format|格式化|初始化)\b', replies.DANGEROUS_COMMAND_BLOCKED),
            (r'\b(shutdown|reboot|restart|关机|重启)\b', replies.DANGEROUS_COMMAND_BLOCKED),
        ]
        
        for pattern, reply in dangerous_patterns:
            if re.search(pattern, text_lower, re.IGNORECASE):
                logger.warning(f"blocked dangerous command: {text[:50]}")
                return reply
        
        injection_patterns = [
            r'[;|&`$]',
            r'\b(eval|exec|system|os\.system|subprocess)\b',
            r'<script|javascript:|on\w+\s*=',
            r'\b(union\s+select|insert\s+into|update\s+\w+\s+set)\b',
        ]
        
        for pattern in injection_patterns:
            if re.search(pattern, text, re.IGNORECASE):
                logger.warning(f"blocked injection attempt: {text[:50]}")
                return replies.INJECTION_ATTEMPT_BLOCKED
        
        return None

    def start(self):
        signal.signal(signal.SIGINT, self._handle_signal)
        signal.signal(signal.SIGTERM, self._handle_signal)

        if not self.ilink.token:
            logger.info("no saved session, starting QR login...")
            if not self.ilink.login():
                logger.error("login failed")
                return

        logger.info(f"bot_id={self.ilink.bot_id}, starting...")
        self.attachments.cleanup_expired()
        self.ilink.notify_start()
        self._running = True
        self._loop()

    def _loop(self):
        logger.info("listening for messages...")
        while self._running:
            try:
                if time.time() - self._last_cleanup > 86400:
                    self.attachments.cleanup_expired()
                    self._last_cleanup = time.time()
                msgs = self.ilink.get_updates()
                for msg in msgs:
                    self._handle_message(msg)
            except Exception as e:
                logger.error(f"loop error: {e}")
                time.sleep(5)

    def _handle_message(self, msg: dict):
        msg_id = self._msg_fingerprint(msg)
        if self._is_duplicate(msg_id):
            logger.info(f"duplicate msg skipped: {msg_id}")
            return

        parsed = self.parser.parse(msg)
        from_user = parsed.user_id
        text = parsed.text
        context_token = parsed.context_token

        has_explicit_quote_in_msg = False
        quoted_attachments = [a for a in parsed.attachments if a.is_quoted]
        
        if parsed.quoted_text:
            logger.info(f"quoted text: {repr(parsed.quoted_text)[:80]}")
            has_explicit_quote_in_msg = True

        if quoted_attachments:
            logger.info(f"found {len(quoted_attachments)} quoted attachment(s)")
            has_explicit_quote_in_msg = True

        if parsed.quoted_timestamp:
            logger.info(f"quoted timestamp: {parsed.quoted_timestamp}")
            has_explicit_quote_in_msg = True

        if has_explicit_quote_in_msg:
            debug_path = self.parser.save_debug_message(msg, self.debug_dir, "quoted_message")
            logger.info(f"saved quoted message debug: {debug_path}")

        if not text and not parsed.attachments:
            return

        logger.info(f"msg from {from_user}: {repr(text)[:50]}... attachments={len(parsed.attachments)} quoted={len(quoted_attachments)} has_quote={has_explicit_quote_in_msg}")

        security_reply = self._check_dangerous_command(text)
        if security_reply:
            logger.info(f"reply to {from_user}: {security_reply[:50]}...")
            self.ilink.send_message(security_reply, from_user, context_token)
            return

        if self._check_pending_report(from_user, text, context_token):
            return

        try:
            config = self.ilink.get_config(from_user, context_token)
            typing_ticket = config.get("typing_ticket", "")
            if typing_ticket:
                self.ilink.send_typing(from_user, typing_ticket)
        except Exception:
            pass

        file_contexts = self._prepare_files(from_user, parsed)
        
        if not file_contexts and parsed.attachments:
            reply = replies.DOWNLOAD_FAILED
            logger.info(f"reply to {from_user}: {reply[:50]}...")
            self.ilink.send_message(reply, from_user, context_token)
            return

        has_explicit_quote = parsed.quoted_text or any(a.is_quoted for a in parsed.attachments) or parsed.quoted_timestamp
        
        if not file_contexts and not has_explicit_quote:
            historical_contexts = self._check_historical_references(from_user, text)
            if historical_contexts:
                file_contexts = historical_contexts
                logger.info(f"found {len(file_contexts)} historical file references")

        if not file_contexts and parsed.quoted_timestamp and not quoted_attachments:
            ts_context = self._find_file_by_timestamp(from_user, parsed.quoted_timestamp)
            if ts_context:
                file_contexts = [ts_context]
                logger.info(f"found file by quoted timestamp: {ts_context.filename}")

        unprocessable_files = [ctx for ctx in file_contexts if getattr(ctx, "error", "") and not getattr(ctx, "content", "")]
        if unprocessable_files:
            reply = self._build_unprocessable_reply(unprocessable_files)
            logger.info(f"reply to {from_user}: {reply[:50]}...")
            self.ilink.send_message(reply, from_user, context_token)
            return

        over_limit_files = [ctx for ctx in file_contexts if getattr(ctx, "over_limit", False)]
        if over_limit_files:
            file_contexts = self._summarize_large_files(from_user, text, context_token, file_contexts, over_limit_files)
            failed_files = [ctx for ctx in file_contexts if getattr(ctx, "error", "").startswith("大文件分块摘要失败") and not getattr(ctx, "content", "")]
            if failed_files:
                reply = self._build_unprocessable_reply(failed_files)
                logger.info(f"reply to {from_user}: {reply[:50]}...")
                self.ilink.send_message(reply, from_user, context_token)
                return

        total_file_tokens = sum(getattr(ctx, "estimated_tokens", 0) for ctx in file_contexts)
        if total_file_tokens > self.max_total_file_tokens:
            file_contexts = self._summarize_large_files(from_user, text, context_token, file_contexts, file_contexts)
            failed_files = [ctx for ctx in file_contexts if getattr(ctx, "error", "").startswith("大文件分块摘要失败") and not getattr(ctx, "content", "")]
            if failed_files:
                reply = self._build_unprocessable_reply(failed_files)
                logger.info(f"reply to {from_user}: {reply[:50]}...")
                self.ilink.send_message(reply, from_user, context_token)
                return

        if file_contexts:
            file_contexts = self._store_file_memories(from_user, text, file_contexts)

        video_url_ctx = self._extract_video_url(text)
        if video_url_ctx:
            file_contexts.append(video_url_ctx)
            text = self._remove_video_url(text)

        has_video = any(getattr(ctx, "mime_type", "").startswith("video/") for ctx in file_contexts)
        has_audio = any(getattr(ctx, "mime_type", "").startswith("audio/") for ctx in file_contexts)
        if has_video:
            self.ilink.send_message(replies.VIDEO_PROCESSING, from_user, context_token)
        elif has_audio:
            self.ilink.send_message(replies.AUDIO_PROCESSING, from_user, context_token)

        context_messages = self.memory.build_context(
            from_user,
            text,
            include_active_file=not bool(file_contexts),
        )
        selected_skills = self.skills.select(text, file_contexts)
        skill_context = self.skills.build_context(selected_skills)
        if skill_context:
            context_messages.append({"role": "system", "content": skill_context})
        reply = self.llm.chat(
            from_user,
            text,
            files=file_contexts,
            context_messages=context_messages,
            record_history=True,
        )
        logger.info(f"reply to {from_user}: {reply[:50]}...")

        self._process_reply(reply, from_user, context_token, file_contexts)
        self.memory.add_turn(from_user, text or "请总结我发送的文件，并指出重点。", reply, file_contexts)

    def _prepare_files(self, from_user: str, parsed) -> list:
        contexts = []
        for attachment in parsed.attachments:
            logger.info(f"attachment: type={attachment.item_type} filename={attachment.filename} mime={attachment.mime_type} size={attachment.size} url={attachment.url[:50] if attachment.url else ''} file_id={attachment.file_id[:20] if attachment.file_id else ''}")
            local_path = None
            try:
                local_path = self.attachments.materialize(from_user, attachment, self.ilink)
            except ValueError as e:
                contexts.append(FileContext(
                    filename=attachment.filename or "未命名文件",
                    path="",
                    mime_type=attachment.mime_type,
                    content="",
                    error=str(e),
                    estimated_tokens=0,
                    token_limit=self.documents.max_file_tokens,
                    over_limit=True,
                ))
                continue
            except Exception as e:
                logger.error(f"attachment materialize failed: {e}")

            if local_path:
                ctx = self.documents.analyze(local_path, attachment.mime_type)
                contexts.append(ctx)
            else:
                debug_path = self.parser.save_debug_message(parsed.raw, self.debug_dir, "attachment_not_materialized")
                logger.info(f"saved attachment debug message: {debug_path}")
        return contexts

    def _check_historical_references(self, user_id: str, text: str) -> list:
        if not text:
            return []
        
        text_lower = text.lower()
        reference_keywords = ["这个", "那个", "刚才", "之前", "上次", "前面", "之前发", "刚才发", "分析", "总结", "看看", "看下"]
        if not any(kw in text_lower for kw in reference_keywords):
            return []
        
        memory = self.memory.get(user_id)
        recent_turns = memory.get("recent_turns", [])
        if not recent_turns:
            return []
        
        # 倒序查找最近一条有文件的消息
        last_turn_with_files = None
        for turn in reversed(recent_turns):
            turn_files = turn.get("files", [])
            if turn_files:
                last_turn_with_files = turn
                break
        
        if not last_turn_with_files:
            return []
        
        turn_files = last_turn_with_files.get("files", [])
        if not turn_files:
            return []
        
        contexts = []
        for file_info in turn_files:
            filename = file_info.get("filename", "")
            if not filename:
                continue
            
            file_path = self._find_historical_file(user_id, filename)
            if not file_path or not file_path.exists():
                logger.info(f"historical file not found: {filename}")
                continue
            
            ctx = self.documents.analyze(file_path, "")
            if not getattr(ctx, "error", "") or getattr(ctx, "content", ""):
                contexts.append(ctx)
                logger.info(f"loaded historical file: {filename}")
            else:
                logger.warning(f"failed to analyze historical file {filename}: {ctx.error}")
        
        return contexts

    def _find_historical_file(self, user_id: str, filename: str) -> Optional[Path]:
        user_dir = self.attachments.base_dir / user_id
        if not user_dir.exists():
            return None
        
        for date_dir in sorted(user_dir.iterdir(), reverse=True):
            if not date_dir.is_dir():
                continue
            file_path = date_dir / filename
            if file_path.exists():
                return file_path
        
        return None

    def _find_file_by_timestamp(self, user_id: str, create_time_ms: int) -> Optional[FileContext]:
        user_dir = self.attachments.base_dir / user_id
        if not user_dir.exists():
            return None
        
        target_ts = create_time_ms / 1000.0
        best_match = None
        best_diff = float("inf")
        
        for date_dir in user_dir.iterdir():
            if not date_dir.is_dir():
                continue
            for file_path in date_dir.iterdir():
                if not file_path.is_file() or file_path.name.startswith("."):
                    continue
                file_ts = file_path.stat().st_mtime
                diff = abs(file_ts - target_ts)
                if diff < best_diff:
                    best_diff = diff
                    best_match = file_path
        
        if best_match and best_diff < 5:
            logger.info(f"timestamp match: {best_match.name} (diff={best_diff:.1f}s)")
            ctx = self.documents.analyze(best_match, "")
            if not getattr(ctx, "error", "") or getattr(ctx, "content", "") or getattr(ctx, "base64_data", ""):
                return ctx
            logger.warning(f"failed to analyze timestamp-matched file: {ctx.error}")
        
        return None

    def _summarize_large_files(self, from_user: str, text: str, context_token: str, all_contexts: list, large_contexts: list) -> list:
        if self.large_file_strategy != "chunk_summary":
            return all_contexts

        notice = self._build_chunking_notice(large_contexts)
        logger.info(f"reply to {from_user}: {notice[:50]}...")
        self.ilink.send_message(notice, from_user, context_token)

        summarized = []
        for ctx in all_contexts:
            if ctx not in large_contexts:
                summarized.append(ctx)
                continue
            try:
                summarized.append(self.llm.summarize_large_file(from_user, text, ctx))
            except Exception as e:
                logger.error(f"large file summary failed: {e}")
                summarized.append(FileContext(
                    filename=ctx.filename,
                    path=ctx.path,
                    mime_type=ctx.mime_type,
                    content="",
                    error=f"大文件分块摘要失败：{e}",
                    estimated_tokens=getattr(ctx, "estimated_tokens", 0),
                    token_limit=getattr(ctx, "token_limit", 0),
                    over_limit=True,
                ))
        return summarized

    def _build_chunking_notice(self, file_contexts: list) -> str:
        lines = [replies.CHUNKING_NOTICE]
        for ctx in file_contexts[:3]:
            lines.append(replies.CHUNKING_FILE_LINE.format(
                filename=ctx.filename,
                tokens=getattr(ctx, 'estimated_tokens', 0),
            ))
        return "\n".join(lines)

    def _build_unprocessable_reply(self, file_contexts: list) -> str:
        lines = [replies.UNPROCESSABLE_HEADER]
        for ctx in file_contexts[:5]:
            error = getattr(ctx, 'error', '')
            if not error:
                error = "暂时无法解析"
            lines.append(f"- {ctx.filename}：{error}")
        lines.append(replies.UNPROCESSABLE_FOOTER)
        return "\n".join(lines)

    def _store_file_memories(self, from_user: str, text: str, file_contexts: list) -> list:
        stored = []
        for ctx in file_contexts:
            if getattr(ctx, "base64_data", ""):
                stored.append(ctx)
                continue

            if getattr(ctx, "error", "").startswith("文件较大，已分成"):
                chunk_summaries = getattr(ctx, "chunk_summaries", [])
                self.memory.add_active_file(from_user, ctx, chunk_summaries=chunk_summaries)
                stored.append(ctx)
                continue

            try:
                ctx = self.llm.summarize_file_for_memory(text, ctx)
            except Exception as e:
                logger.error(f"file memory summary failed: {e}")
                ctx.summary = getattr(ctx, "content", "")[:4000]
            self.memory.add_active_file(from_user, ctx, chunk_summaries=[])
            stored.append(ctx)
        return stored

    def _process_reply(self, reply: str, from_user: str, context_token: str, file_contexts: list):
        char_count = len(reply)

        if char_count <= self.max_chat_chars:
            self.ilink.send_message(reply, from_user, context_token)
            return

        if char_count <= self.auto_split_threshold:
            chunks = self._split_reply(reply)
            for i, chunk in enumerate(chunks):
                prefix = f"({i + 1}/{len(chunks)}) " if len(chunks) > 1 else ""
                self.ilink.send_message(prefix + chunk, from_user, context_token)
                if i < len(chunks) - 1:
                    time.sleep(self.split_delay)
            return

        summary = self._extract_summary(reply)
        self.ilink.send_message(summary, from_user, context_token)
        self.ilink.send_message(
            replies.LONG_REPLY_SUMMARY_PROMPT,
            from_user, context_token,
        )
        self._pending_file_reports[from_user] = {
            "content": reply,
            "file_contexts": file_contexts,
            "created_at": time.time(),
        }

    def _split_reply(self, reply: str) -> list[str]:
        max_chars = self.max_chat_chars
        sections = []
        current = []
        current_len = 0

        for line in reply.splitlines(keepends=True):
            line_len = len(line)
            if current_len + line_len > max_chars and current:
                sections.append("".join(current).strip())
                current = []
                current_len = 0
            current.append(line)
            current_len += line_len

        if current:
            sections.append("".join(current).strip())

        result = []
        for section in sections:
            if len(section) <= max_chars:
                result.append(section)
            else:
                while section:
                    if len(section) <= max_chars:
                        result.append(section)
                        break
                    cut = section.rfind("\n", 0, max_chars)
                    if cut == -1:
                        cut = section.rfind("。", 0, max_chars)
                    if cut == -1:
                        cut = section.rfind("；", 0, max_chars)
                    if cut == -1:
                        cut = section.rfind("，", 0, max_chars)
                    if cut == -1 or cut < max_chars // 2:
                        cut = max_chars
                    result.append(section[:cut + 1].strip())
                    section = section[cut + 1:].strip()

        return [s for s in result if s]

    def _extract_summary(self, reply: str) -> str:
        max_chars = self.max_chat_chars - 50
        lines = reply.splitlines()
        summary_lines = []
        current_len = 0

        for line in lines:
            stripped = line.strip()
            if not stripped:
                continue

            is_heading = (
                stripped.startswith("#")
                or stripped.startswith("**")
                or stripped.startswith("##")
                or (len(stripped) < 30 and stripped.endswith("："))
                or (len(stripped) < 30 and stripped.endswith(":"))
            )

            is_conclusion = any(kw in stripped for kw in [
                "结论", "总结", "核心", "要点", "关键", "建议", "风险",
                "重要", "注意", "总体", "概要", "摘要",
            ])

            if is_heading or is_conclusion:
                if current_len + len(stripped) + 1 <= max_chars:
                    summary_lines.append(stripped)
                    current_len += len(stripped) + 1
                else:
                    break

        if not summary_lines:
            for line in lines:
                stripped = line.strip()
                if not stripped:
                    continue
                if current_len + len(stripped) + 1 > max_chars:
                    break
                summary_lines.append(stripped)
                current_len += len(stripped) + 1

        if not summary_lines:
            return reply[:max_chars] + "..."

        return "\n".join(summary_lines)

    def _check_pending_report(self, from_user: str, text: str, context_token: str) -> bool:
        if from_user not in self._pending_file_reports:
            return False

        if not text:
            return False

        trigger_words = ["要", "好的", "行", "可以", "发", "详细", "完整", "报告", "嗯", "好"]
        text_stripped = text.strip()
        if not any(text_stripped == w or text_stripped.startswith(w) for w in trigger_words):
            del self._pending_file_reports[from_user]
            return False

        pending = self._pending_file_reports.pop(from_user)
        if time.time() - pending["created_at"] > 300:
            self.ilink.send_message(replies.REPORT_EXPIRED, from_user, context_token)
            return True

        full_content = pending["content"]
        chunks = self._split_reply(full_content)
        self.ilink.send_message(replies.REPORT_SENDING_NOTICE.format(count=len(chunks)), from_user, context_token)
        time.sleep(self.split_delay)
        for i, chunk in enumerate(chunks):
            prefix = f"({i + 1}/{len(chunks)}) "
            self.ilink.send_message(prefix + chunk, from_user, context_token)
            if i < len(chunks) - 1:
                time.sleep(self.split_delay)
        return True

    _VIDEO_URL_PATTERN = re.compile(
        r'https?://[^\s<>"\']+\.(?:mp4|mov|avi|mkv|webm|flv)(?:\?[^\s<>"\']*)?',
        re.IGNORECASE,
    )

    def _extract_video_url(self, text: str) -> Optional[FileContext]:
        if not text:
            return None
        match = self._VIDEO_URL_PATTERN.search(text)
        if not match:
            return None
        url = match.group(0)
        logger.info(f"detected video URL in text: {url[:80]}...")
        return FileContext(
            filename=url.split("/")[-1].split("?")[0] or "video.mp4",
            path="",
            mime_type="video/mp4",
            content="",
            source_url=url,
        )

    def _remove_video_url(self, text: str) -> str:
        return self._VIDEO_URL_PATTERN.sub("", text).strip()

    def _msg_fingerprint(self, msg: dict) -> str:
        msg_id = msg.get("msg_id") or msg.get("client_id") or ""
        from_user = msg.get("from_user_id", "")
        if msg_id:
            return f"{from_user}:{msg_id}"
        text_parts = []
        for item in msg.get("item_list", []):
            if item.get("type") == 1:
                text_parts.append(item.get("text_item", {}).get("text", ""))
        raw = f"{from_user}:{':'.join(text_parts)}:{msg.get('context_token', '')[:20]}"
        return hashlib.md5(raw.encode("utf-8")).hexdigest()

    def _is_duplicate(self, msg_id: str) -> bool:
        now = time.time()
        if msg_id in self._seen_msgs:
            return True
        self._seen_msgs[msg_id] = now
        expired = [key for key, ts in self._seen_msgs.items() if now - ts > self._seen_msgs_ttl]
        for key in expired:
            del self._seen_msgs[key]
        while len(self._seen_msgs) > self._seen_msgs_max:
            self._seen_msgs.popitem(last=False)
        return False


if __name__ == "__main__":
    _load_dotenv()
    if not check_single_instance():
        sys.exit(1)
    bot = WeChatBot()
    bot.start()
    cleanup_pid_file()
