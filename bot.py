import argparse
import fcntl
import hashlib
import json
import logging
import logging.handlers
import os
import re
import signal
import sys
import threading
import time
import uuid
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


# 只允许 .env 设置这些应用相关的环境变量
_ALLOWED_ENV_KEYS = frozenset({
    "LLM_API_KEY",
    "LLM_BASE_URL",
    "LLM_MODEL",
    "ILINK_BOT_TOKEN",
    "ILINK_BOT_ID",
    "ILINK_USER_ID",
    "ILINK_API_BASE_URL",
})


def _load_dotenv(path: str = ".env"):
    env_path = Path(path)
    if not env_path.exists():
        return [], []
    loaded_keys = []
    skipped_keys = []
    try:
        for line in env_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip().strip("\"'")
            if not key or not value:
                continue
            if key not in _ALLOWED_ENV_KEYS:
                continue
            if key in os.environ and os.environ[key]:
                skipped_keys.append(key)
                continue
            os.environ[key] = value
            loaded_keys.append(key)
    except (IOError, UnicodeDecodeError):
        pass
    return loaded_keys, skipped_keys

PID_FILE = Path("data/bot.pid")

# 配置日志轮转：按文件大小轮转，保留最近3个备份
def setup_logging():
    log_dir = Path("data")
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "bot.log"
    
    # 从 config.json 读取日志配置
    log_cfg = {}
    config_path = Path("config.json")
    if config_path.exists():
        try:
            config_data = json.loads(config_path.read_text(encoding="utf-8"))
            log_cfg = config_data.get("logging", {})
        except (json.JSONDecodeError, IOError) as e:
            pass  # 使用默认值
    
    # 日志格式
    formatter = logging.Formatter(
        "%(asctime)s [%(name)s] %(levelname)s %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    
    # 获取配置参数
    level_str = log_cfg.get("level", "INFO")
    level = getattr(logging, level_str.upper(), logging.INFO)
    max_bytes = log_cfg.get("max_bytes", 10 * 1024 * 1024)
    backup_count = log_cfg.get("backup_count", 3)
    encoding = log_cfg.get("encoding", "utf-8")
    
    # 使用 RotatingFileHandler 确保 max_bytes 生效
    file_handler = logging.handlers.RotatingFileHandler(
        log_file,
        maxBytes=max_bytes,
        backupCount=backup_count,
        encoding=encoding
    )
    file_handler.setFormatter(formatter)
    
    # 控制台处理器
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    
    # 根日志配置
    root_logger = logging.getLogger()
    root_logger.setLevel(level)
    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)

setup_logging()
logger = logging.getLogger("bot")


_lock_fd = None


def check_single_instance():
    """检查是否已有实例在运行，使用文件锁防止竞态条件"""
    global _lock_fd
    
    # 如果已有锁，先释放
    if _lock_fd is not None:
        try:
            fcntl.flock(_lock_fd.fileno(), fcntl.LOCK_UN)
            _lock_fd.close()
        except Exception:
            pass
        _lock_fd = None
    
    PID_FILE.parent.mkdir(parents=True, exist_ok=True)
    lock_file = PID_FILE.with_suffix('.lock')
    
    try:
        _lock_fd = open(lock_file, 'w')
        fcntl.flock(_lock_fd.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except (IOError, OSError):
        logger.error("无法获取进程锁，可能已有其他实例在运行")
        if _lock_fd:
            _lock_fd.close()
            _lock_fd = None
        return False
    
    if PID_FILE.exists():
        try:
            with open(PID_FILE, 'r') as f:
                old_pid = int(f.read().strip())
            
            try:
                os.kill(old_pid, 0)
                logger.error(f"机器人已在运行中 (PID: {old_pid})，请先停止旧进程")
                logger.info(f"停止命令: kill {old_pid}")
                fcntl.flock(_lock_fd.fileno(), fcntl.LOCK_UN)
                _lock_fd.close()
                _lock_fd = None
                return False
            except OSError:
                logger.info(f"发现旧的 PID 文件，但进程 {old_pid} 已不存在，将清理并启动")
                PID_FILE.unlink(missing_ok=True)
        except (ValueError, IOError) as e:
            logger.warning(f"读取 PID 文件失败: {e}，将重新创建")
            PID_FILE.unlink(missing_ok=True)
    
    try:
        PID_FILE.write_text(str(os.getpid()))
        logger.info(f"进程锁已创建 (PID: {os.getpid()})")
        return True
    except Exception as e:
        logger.error(f"创建 PID 文件失败: {e}")
        fcntl.flock(_lock_fd.fileno(), fcntl.LOCK_UN)
        _lock_fd.close()
        _lock_fd = None
        return False


def cleanup_pid_file():
    """清理 PID 文件和锁文件"""
    global _lock_fd
    try:
        if _lock_fd:
            fcntl.flock(_lock_fd.fileno(), fcntl.LOCK_UN)
            _lock_fd.close()
            _lock_fd = None
    except Exception:
        pass
    try:
        if PID_FILE.exists():
            PID_FILE.unlink()
        lock_file = PID_FILE.with_suffix('.lock')
        if lock_file.exists():
            lock_file.unlink()
        logger.info("PID 文件和锁文件已清理")
    except Exception as e:
        logger.warning(f"清理 PID 文件失败: {e}")


class WeChatBot:
    def __init__(self, session_path: str = "session.json", shared: dict = None):
        self.account_id = Path(session_path).stem
        # 每个账号有带前缀的 logger
        self.logger = logging.getLogger(f"bot[{self.account_id}]")
        self.config = self._load_config()
        bot_cfg = self.config.get("bot", {})
        channel_version = bot_cfg.get("channel_version", "2.1.10")
        self.ilink = ILinkClient(config_path=session_path, channel_version=channel_version)
        self._running = False
        self._seen_msgs: OrderedDict[str, float] = OrderedDict()
        self._seen_msgs_lock = threading.Lock()
        self._seen_msgs_ttl = 300
        self._seen_msgs_max = 500
        # 按账号+用户隔离待发送报告，避免跨账号数据混淆
        self._pending_file_reports: dict[str, dict] = {}
        self._pending_reports_max_size = 100
        self._pending_reports_ttl = 300
        self._last_pending_cleanup = 0.0
        self._last_cleanup = 0.0
        self._content_fingerprints: dict[str, float] = {}
        self._content_fp_lock = threading.Lock()
        self._content_fp_ttl = 10
        self._pending_attachments: dict[str, dict] = {}
        self._pending_attachments_lock = threading.Lock()
        self._pending_skill_menus: dict[str, dict] = {}
        self._pending_skill_menus_lock = threading.Lock()
        self._selected_report_types: dict[str, tuple[str, float]] = {}
        self._report_type_ttl = 300
        self.attachment_wait_seconds = bot_cfg.get("attachment_wait_seconds", 15)
        self.debug_dir = Path("data/debug_messages")

        if shared:
            self.parser = shared["parser"]
            self.attachments = shared["attachments"]
            self.documents = shared["documents"]
            self.memory = shared["memory"]
            self.llm = shared["llm"]
            self.skills = shared["skills"]
            self.max_total_file_tokens = shared["max_total_file_tokens"]
            self.large_file_strategy = shared["large_file_strategy"]
            self.max_chat_chars = shared["max_chat_chars"]
            self.auto_split_threshold = shared["auto_split_threshold"]
            self.file_output_threshold = shared["file_output_threshold"]
            self.split_delay = shared["split_delay"]
            self._seen_msgs = shared["seen_msgs"]
            self._seen_msgs_lock = shared["seen_msgs_lock"]
            self._content_fingerprints = shared["content_fingerprints"]
            self._content_fp_lock = shared["content_fp_lock"]
            return

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
        reply_cfg = self.config.get("reply", {})
        self.max_chat_chars = reply_cfg.get("max_chat_chars", 800)
        self.auto_split_threshold = reply_cfg.get("auto_split_threshold", 2000)
        self.file_output_threshold = reply_cfg.get("file_output_threshold", 3000)
        self.split_delay = reply_cfg.get("split_delay_seconds", 0.5)

    def _load_config(self) -> dict:
        return self._load_config_static()

    @staticmethod
    def _load_config_static() -> dict:
        path = Path("config.json")
        if not path.exists():
            return {}
        return json.loads(path.read_text(encoding="utf-8"))

    def _handle_signal(self, sig, frame):
        self.logger.info(f"shutting down...")
        self._running = False
        try:
            self.ilink.notify_stop()
        except Exception:
            pass

    def _check_dangerous_command(self, text: str) -> Optional[str]:
        if not text:
            return None
        
        text_lower = text.lower().strip()
        
        command_patterns = [
            (r'(?:^|\s)(rm\s+-|del\s+/|delete\s+from|drop\s+table|truncate\s+)', replies.DANGEROUS_COMMAND_BLOCKED),
            (r'(?:^|\s)(pkill|killall)\b', replies.DANGEROUS_COMMAND_BLOCKED),
            (r'(?:^|\s)(shutdown|reboot)\s*', replies.DANGEROUS_COMMAND_BLOCKED),
            (r'(清除所有|删除全部|清空所有|抹除所有)', replies.DANGEROUS_COMMAND_BLOCKED),
        ]
        
        for pattern, reply in command_patterns:
            if re.search(pattern, text_lower, re.IGNORECASE):
                self.logger.warning(f"blocked dangerous command: {text[:50]}")
                return reply
        
        injection_patterns = [
            r'[;|&`]',
            r'<script|javascript:|on\w+\s*=',
            r'\b(union\s+select|insert\s+into|update\s+\w+\s+set)\b',
        ]
        
        for pattern in injection_patterns:
            if re.search(pattern, text, re.IGNORECASE):
                self.logger.warning(f"blocked injection attempt: {text[:50]}")
                return replies.INJECTION_ATTEMPT_BLOCKED
        
        return None

    def start(self):
        signal.signal(signal.SIGINT, self._handle_signal)
        signal.signal(signal.SIGTERM, self._handle_signal)

        if not self.ilink.token:
            self.logger.info(f"no saved session, starting QR login...")
            if not self.ilink.login():
                self.logger.error(f"login failed")
                return

        self._run()

    def _run(self):
        self.logger.info(f"bot_id={self.ilink.bot_id}, starting...")
        self.attachments.cleanup_expired()
        self.ilink.notify_start()
        self._running = True
        self._loop()

    def _loop(self):
        self.logger.info("listening for messages...")
        consecutive_failures = 0
        last_success_time = time.time()
        while self._running:
            try:
                if time.time() - self._last_cleanup > 86400:
                    self.attachments.cleanup_expired()
                    self._last_cleanup = time.time()
                
                self._cleanup_pending_reports()
                self._flush_pending_attachments()
                
                msgs = self.ilink.get_updates()
                consecutive_failures = 0
                last_success_time = time.time()
                if msgs:
                    self.logger.info(f"get_updates returned {len(msgs)} message(s)")
                for msg in msgs:
                    try:
                        self._handle_message(msg)
                    except Exception as msg_err:
                        self.logger.error(f"message handling error: {msg_err}", exc_info=True)
            except Exception as e:
                consecutive_failures += 1
                self.logger.error(f"loop error ({consecutive_failures}x): {e}")
                
                if consecutive_failures >= 5:
                    gap = time.time() - last_success_time
                    if gap > 60:
                        self.logger.warning(
                            f"network may have been down for {gap:.0f}s, "
                            f"checking session..."
                        )
                        try:
                            self.ilink.notify_start()
                            self.logger.info("session recovered after network gap")
                        except Exception as re_err:
                            self.logger.error(f"session recovery failed: {re_err}")
                    consecutive_failures = 0
                    time.sleep(10)
                else:
                    time.sleep(5)
    
    def _memory_key(self, user_id: str) -> str:
        return f"{self.account_id}:{user_id}"

    def _pending_key(self, from_user: str) -> str:
        """生成带账号前缀的待发送报告 key，确保多账号隔离"""
        return f"{self.account_id}:{from_user}"

    def _is_multimodal_attachment(self, attachment) -> bool:
        mime = (attachment.mime_type or "").lower()
        return mime.startswith("image/") or mime.startswith("audio/") or mime.startswith("video/")

    def _all_multimodal(self, attachments: list) -> bool:
        non_quoted = [a for a in attachments if not a.is_quoted]
        return bool(non_quoted) and all(self._is_multimodal_attachment(a) for a in non_quoted)

    def _multimodal_ack_message(self, attachments: list) -> str:
        non_quoted = [a for a in attachments if not a.is_quoted]
        has_image = any(a.mime_type.startswith("image/") for a in non_quoted)
        has_audio = any(a.mime_type.startswith("audio/") for a in non_quoted)
        has_video = any(a.mime_type.startswith("video/") for a in non_quoted)
        types_count = sum([has_image, has_audio, has_video])
        if types_count > 1:
            return replies.MULTIMODAL_RECEIVED_MULTI
        if has_audio:
            return replies.MULTIMODAL_RECEIVED_AUDIO
        if has_video:
            return replies.MULTIMODAL_RECEIVED_VIDEO
        return replies.MULTIMODAL_RECEIVED_IMAGE

    def _buffer_attachments(self, from_user: str, parsed, context_token: str):
        key = self._memory_key(from_user)
        with self._pending_attachments_lock:
            existing = self._pending_attachments.get(key)
            if existing:
                existing["parsed"].attachments.extend(parsed.attachments)
                existing["context_token"] = context_token
                existing["timestamp"] = time.time()
                self.logger.info(f"appended {len(parsed.attachments)} attachment(s) to buffer for {from_user}, total={len(existing['parsed'].attachments)}")
                return
            self._pending_attachments[key] = {
                "parsed": parsed,
                "context_token": context_token,
                "timestamp": time.time(),
            }
            self.logger.info(f"buffered {len(parsed.attachments)} multimodal attachment(s) for {from_user}, waiting {self.attachment_wait_seconds}s for text...")
        ack = self._multimodal_ack_message(parsed.attachments)
        self.ilink.send_message(ack, from_user, context_token)

    def _merge_buffered_attachments(self, from_user: str, parsed):
        key = self._memory_key(from_user)
        with self._pending_attachments_lock:
            buffered = self._pending_attachments.pop(key, None)
        if not buffered:
            return
        buffered_parsed = buffered["parsed"]
        non_quoted_buffered = [a for a in buffered_parsed.attachments if not a.is_quoted]
        if non_quoted_buffered:
            parsed.attachments = non_quoted_buffered + parsed.attachments
            self.logger.info(f"merged {len(non_quoted_buffered)} buffered attachment(s) with text for {from_user}")

    def _flush_pending_attachments(self):
        now = time.time()
        expired_keys = []
        with self._pending_attachments_lock:
            for key, entry in self._pending_attachments.items():
                if now - entry["timestamp"] >= self.attachment_wait_seconds:
                    expired_keys.append(key)
        for key in expired_keys:
            with self._pending_attachments_lock:
                entry = self._pending_attachments.pop(key, None)
            if not entry:
                continue
            parsed = entry["parsed"]
            context_token = entry["context_token"]
            from_user = parsed.user_id
            self.logger.info(f"flushing buffered attachments for {from_user} (timeout {self.attachment_wait_seconds}s, auto-analyzing)")
            self.ilink.send_message(replies.MULTIMODAL_AUTO_ANALYZE, from_user, context_token)
            self._process_buffered_message(from_user, parsed, context_token, auto_analyze=True)

    def _process_buffered_message(self, from_user: str, parsed, context_token: str, auto_analyze: bool = False):
        self.logger.info(f"processing buffered message from {from_user}: attachments={len(parsed.attachments)} auto_analyze={auto_analyze}")

        try:
            config = self.ilink.get_config(from_user, context_token)
            typing_ticket = config.get("typing_ticket", "")
            if typing_ticket:
                self.ilink.send_typing(from_user, typing_ticket)
        except Exception:
            pass

        file_contexts = self._prepare_files(from_user, parsed)

        if not file_contexts and parsed.attachments:
            self.ilink.send_message(replies.DOWNLOAD_FAILED, from_user, context_token)
            return

        unprocessable_files = [ctx for ctx in file_contexts if getattr(ctx, "error", "") and not getattr(ctx, "content", "")]
        if unprocessable_files:
            reply = self._build_unprocessable_reply(unprocessable_files)
            self.ilink.send_message(reply, from_user, context_token)
            return

        over_limit_files = [ctx for ctx in file_contexts if getattr(ctx, "over_limit", False)]
        if over_limit_files:
            text = parsed.text or ""
            file_contexts = self._summarize_large_files(from_user, text, context_token, file_contexts, over_limit_files)
            failed_files = [ctx for ctx in file_contexts if getattr(ctx, "error", "").startswith("大文件分块摘要失败") and not getattr(ctx, "content", "")]
            if failed_files:
                reply = self._build_unprocessable_reply(failed_files)
                self.ilink.send_message(reply, from_user, context_token)
                return

        total_file_tokens = sum(getattr(ctx, "estimated_tokens", 0) for ctx in file_contexts)
        if total_file_tokens > self.max_total_file_tokens:
            text = parsed.text or ""
            file_contexts = self._summarize_large_files(from_user, text, context_token, file_contexts, file_contexts)
            failed_files = [ctx for ctx in file_contexts if getattr(ctx, "error", "").startswith("大文件分块摘要失败") and not getattr(ctx, "content", "")]
            if failed_files:
                reply = self._build_unprocessable_reply(failed_files)
                self.ilink.send_message(reply, from_user, context_token)
                return

        if file_contexts:
            file_contexts = self._store_file_memories(from_user, parsed.text or "", file_contexts)

        has_video = any(getattr(ctx, "mime_type", "").startswith("video/") for ctx in file_contexts)
        has_audio = any(getattr(ctx, "mime_type", "").startswith("audio/") for ctx in file_contexts)
        if has_video:
            self.ilink.send_message(replies.VIDEO_PROCESSING, from_user, context_token)
        elif has_audio:
            self.ilink.send_message(replies.AUDIO_PROCESSING, from_user, context_token)

        text = parsed.text or ""
        mem_key = self._memory_key(from_user)
        context_messages = self.memory.build_context(
            mem_key,
            text,
            include_active_file=not bool(file_contexts),
        )
        selected_skills = self.skills.select(text, file_contexts)
        skill_context = self.skills.build_context(selected_skills)

        skill_context = self._resolve_skill_menus(selected_skills, from_user, text, file_contexts, context_token, skill_context, skip_menu=auto_analyze)
        if skill_context is None:
            return

        if skill_context:
            context_messages.append({"role": "system", "content": skill_context})

        has_multimodal_files = any(getattr(ctx, "base64_data", "") or getattr(ctx, "source_url", "") for ctx in file_contexts)
        self.logger.info(f"LLM call (buffered): user={from_user} text={repr(text)[:40]} files={len(file_contexts)} multimodal={has_multimodal_files}")
        reply = self.llm.chat(
            mem_key,
            text,
            files=file_contexts,
            context_messages=context_messages,
            record_history=True,
        )
        self.logger.info(f"reply to {from_user}: {reply[:50]}...")

        self._process_reply(reply, from_user, context_token, file_contexts)
        self.memory.add_turn(mem_key, text or "请总结我发送的文件，并指出重点。", reply, file_contexts)

    def _cleanup_pending_reports(self):
        """定期清理过期的待发送报告，防止内存泄露"""
        now = time.time()
        
        # 每60秒执行一次清理
        if now - self._last_pending_cleanup < 60:
            return
        
        self._last_pending_cleanup = now
        
        # 清理过期条目
        expired_keys = [
            k for k, p in self._pending_file_reports.items() 
            if now - p["created_at"] > self._pending_reports_ttl
        ]
        for k in expired_keys:
            del self._pending_file_reports[k]
        
        # 如果超过最大数量，删除最旧的条目
        if len(self._pending_file_reports) > self._pending_reports_max_size:
            sorted_items = sorted(
                self._pending_file_reports.items(),
                key=lambda x: x[1]["created_at"]
            )
            for k, _ in sorted_items[:len(sorted_items) - self._pending_reports_max_size]:
                del self._pending_file_reports[k]
            self.logger.warning(
                f"pending reports exceeded max size, cleaned up to {self._pending_reports_max_size}"
            )

    def _handle_message(self, msg: dict):
        msg_id = self._msg_fingerprint(msg)
        if self._is_duplicate(msg_id):
            self.logger.info(f"duplicate msg skipped: {msg_id}")
            return

        content_fp = self._content_fingerprint(msg)
        if content_fp and self._is_content_duplicate(content_fp):
            self.logger.info(f"content duplicate skipped: {content_fp[:60]}")
            return

        raw_msg_id = msg.get("msg_id") or msg.get("client_id") or "none"
        item_types = [item.get("type") for item in msg.get("item_list", [])]
        self.logger.info(f"msg raw: msg_id={raw_msg_id} item_types={item_types} content_fp={content_fp[:16]}")

        parsed = self.parser.parse(msg)
        from_user = parsed.user_id
        text = parsed.text
        context_token = parsed.context_token

        has_explicit_quote_in_msg = False
        quoted_attachments = [a for a in parsed.attachments if a.is_quoted]
        
        if parsed.quoted_text:
            self.logger.info(f"quoted text: {repr(parsed.quoted_text)[:80]}")
            has_explicit_quote_in_msg = True

        if quoted_attachments:
            self.logger.info(f"found {len(quoted_attachments)} quoted attachment(s)")
            has_explicit_quote_in_msg = True

        if parsed.quoted_timestamp:
            self.logger.info(f"quoted timestamp: {parsed.quoted_timestamp}")
            has_explicit_quote_in_msg = True

        if has_explicit_quote_in_msg:
            debug_path = self.parser.save_debug_message(msg, self.debug_dir, "quoted_message")
            self.logger.info(f"saved quoted message debug: {debug_path}")

        if not text and not parsed.attachments:
            return

        if not text and not has_explicit_quote_in_msg and self._all_multimodal(parsed.attachments):
            self._buffer_attachments(from_user, parsed, context_token)
            return

        if text:
            self._merge_buffered_attachments(from_user, parsed)

        self.logger.info(f"msg from {from_user}: {repr(text)[:50]}... attachments={len(parsed.attachments)} quoted={len(quoted_attachments)} has_quote={has_explicit_quote_in_msg}")

        security_reply = self._check_dangerous_command(text)
        if security_reply:
            self.logger.info(f"reply to {from_user}: {security_reply[:50]}...")
            self.ilink.send_message(security_reply, from_user, context_token)
            return

        menu_selection = self._check_menu_selection(from_user, text)
        is_menu_replay = False
        if menu_selection:
            self.logger.info(f"menu selection from {from_user}: {menu_selection['report_type']}")
            self._set_selected_report_type(from_user, menu_selection["report_type"])
            text = menu_selection["original_text"]
            file_contexts = menu_selection["file_contexts"]
            is_menu_replay = True
            self.logger.info(f"replaying original request: {repr(text)[:50]}... with {len(file_contexts)} file(s)")
        else:
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
        
        if not is_menu_replay:
            if not file_contexts and parsed.attachments:
                reply = replies.DOWNLOAD_FAILED
                self.logger.info(f"reply to {from_user}: {reply[:50]}...")
                self.ilink.send_message(reply, from_user, context_token)
                return

            has_explicit_quote = parsed.quoted_text or any(a.is_quoted for a in parsed.attachments) or parsed.quoted_timestamp
            
            if not file_contexts and not has_explicit_quote:
                historical_contexts = self._check_historical_references(from_user, text)
                if historical_contexts:
                    file_contexts = historical_contexts
                    self.logger.info(f"found {len(file_contexts)} historical file references")

            if not file_contexts and parsed.quoted_timestamp and not quoted_attachments:
                ts_context = self._find_file_by_timestamp(from_user, parsed.quoted_timestamp)
                if ts_context:
                    file_contexts = [ts_context]
                    self.logger.info(f"found file by quoted timestamp: {ts_context.filename}")

            unprocessable_files = [ctx for ctx in file_contexts if getattr(ctx, "error", "") and not getattr(ctx, "content", "")]
            if unprocessable_files:
                reply = self._build_unprocessable_reply(unprocessable_files)
                self.logger.info(f"reply to {from_user}: {reply[:50]}...")
                self.ilink.send_message(reply, from_user, context_token)
                return

            over_limit_files = [ctx for ctx in file_contexts if getattr(ctx, "over_limit", False)]
            if over_limit_files:
                file_contexts = self._summarize_large_files(from_user, text, context_token, file_contexts, over_limit_files)
                failed_files = [ctx for ctx in file_contexts if getattr(ctx, "error", "").startswith("大文件分块摘要失败") and not getattr(ctx, "content", "")]
                if failed_files:
                    reply = self._build_unprocessable_reply(failed_files)
                    self.logger.info(f"reply to {from_user}: {reply[:50]}...")
                    self.ilink.send_message(reply, from_user, context_token)
                    return

            total_file_tokens = sum(getattr(ctx, "estimated_tokens", 0) for ctx in file_contexts)
            if total_file_tokens > self.max_total_file_tokens:
                file_contexts = self._summarize_large_files(from_user, text, context_token, file_contexts, file_contexts)
                failed_files = [ctx for ctx in file_contexts if getattr(ctx, "error", "").startswith("大文件分块摘要失败") and not getattr(ctx, "content", "")]
                if failed_files:
                    reply = self._build_unprocessable_reply(failed_files)
                    self.logger.info(f"reply to {from_user}: {reply[:50]}...")
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

        mem_key = self._memory_key(from_user)
        context_messages = self.memory.build_context(
            mem_key,
            text,
            include_active_file=not bool(file_contexts),
        )
        selected_skills = self.skills.select(text, file_contexts)
        skill_context = self.skills.build_context(selected_skills)

        skill_context = self._resolve_skill_menus(selected_skills, from_user, text, file_contexts, context_token, skill_context)
        if skill_context is None:
            return

        if skill_context:
            context_messages.append({"role": "system", "content": skill_context})
        has_multimodal_files = any(getattr(ctx, "base64_data", "") or getattr(ctx, "source_url", "") for ctx in file_contexts)
        self.logger.info(f"LLM call: user={from_user} text={repr(text)[:40]} files={len(file_contexts)} multimodal={has_multimodal_files} context_msgs={len(context_messages)}")
        reply = self.llm.chat(
            mem_key,
            text,
            files=file_contexts,
            context_messages=context_messages,
            record_history=True,
        )
        self.logger.info(f"reply to {from_user}: {reply[:50]}...")

        self._process_reply(reply, from_user, context_token, file_contexts)
        self.memory.add_turn(mem_key, text or "请总结我发送的文件，并指出重点。", reply, file_contexts)

    def _prepare_files(self, from_user: str, parsed) -> list:
        contexts = []
        for attachment in parsed.attachments:
            self.logger.info(f"attachment: type={attachment.item_type} filename={attachment.filename} mime={attachment.mime_type} size={attachment.size} url={attachment.url[:50] if attachment.url else ''} file_id={attachment.file_id[:20] if attachment.file_id else ''}")
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
                self.logger.error(f"attachment materialize failed: {e}")

            if local_path:
                ctx = self.documents.analyze(local_path, attachment.mime_type)
                contexts.append(ctx)
            else:
                debug_path = self.parser.save_debug_message(parsed.raw, self.debug_dir, "attachment_not_materialized")
                self.logger.info(f"saved attachment debug message: {debug_path}")
        return contexts

    def _check_historical_references(self, user_id: str, text: str) -> list:
        if not text:
            return []
        
        text_lower = text.lower()
        strong_patterns = [
            "这个文件", "那个文件", "刚才的文件", "之前的文件", "上次的文件",
            "这个文档", "那个文档", "刚才的文档", "之前的文档",
            "这个报告", "那个报告", "刚才的报告",
            "这个视频", "那个视频", "刚才的视频",
            "这个图片", "那个图片", "刚才的图片",
            "这个音频", "那个音频", "刚才的音频",
            "这个PPT", "那个PPT", "这个Excel", "那个Excel",
            "这个Word", "那个Word", "这个PDF", "那个PDF",
            "刚才发的", "之前发的", "上次发的", "前面发的",
            "刚才那个", "之前那个", "上次那个",
        ]
        ref_words = ["这个", "那个", "刚才", "之前", "上次", "前面"]
        file_words = [
            "文件", "文档", "报告", "视频", "图片", "音频",
            "ppt", "pptx", "excel", "xlsx", "word", "docx", "pdf",
            "csv", "txt",
        ]
        has_strong = any(p in text_lower for p in strong_patterns)
        has_weak = (
            any(r in text_lower for r in ref_words)
            and any(f in text_lower for f in file_words)
        )
        if not has_strong and not has_weak:
            return []
        
        memory = self.memory.get(self._memory_key(user_id))
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
                self.logger.info(f"historical file not found: {filename}")
                continue
            
            ctx = self.documents.analyze(file_path, "")
            if not getattr(ctx, "error", "") or getattr(ctx, "content", ""):
                contexts.append(ctx)
                self.logger.info(f"loaded historical file: {filename}")
            else:
                self.logger.warning(f"failed to analyze historical file {filename}: {ctx.error}")
        
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
            self.logger.info(f"timestamp match: {best_match.name} (diff={best_diff:.1f}s)")
            ctx = self.documents.analyze(best_match, "")
            if not getattr(ctx, "error", "") or getattr(ctx, "content", "") or getattr(ctx, "base64_data", ""):
                return ctx
            self.logger.warning(f"failed to analyze timestamp-matched file: {ctx.error}")
        
        return None

    def _summarize_large_files(self, from_user: str, text: str, context_token: str, all_contexts: list, large_contexts: list) -> list:
        if self.large_file_strategy != "chunk_summary":
            return all_contexts

        notice = self._build_chunking_notice(large_contexts)
        self.logger.info(f"reply to {from_user}: {notice[:50]}...")
        self.ilink.send_message(notice, from_user, context_token)

        summarized = []
        for ctx in all_contexts:
            if ctx not in large_contexts:
                summarized.append(ctx)
                continue
            try:
                summarized.append(self.llm.summarize_large_file(from_user, text, ctx))
            except Exception as e:
                self.logger.error(f"large file summary failed: {e}")
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
        mem_key = self._memory_key(from_user)
        for ctx in file_contexts:
            if getattr(ctx, "base64_data", ""):
                stored.append(ctx)
                continue

            if getattr(ctx, "error", "").startswith("文件较大，已分成"):
                chunk_summaries = getattr(ctx, "chunk_summaries", [])
                self.memory.add_active_file(mem_key, ctx, chunk_summaries=chunk_summaries)
                stored.append(ctx)
                continue

            try:
                ctx = self.llm.summarize_file_for_memory(text, ctx)
            except Exception as e:
                self.logger.error(f"file memory summary failed: {e}")
                ctx.summary = getattr(ctx, "content", "")[:4000]
            self.memory.add_active_file(mem_key, ctx, chunk_summaries=[])
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
        pending_key = self._pending_key(from_user)
        self._pending_file_reports[pending_key] = {
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
        pending_key = self._pending_key(from_user)
        if pending_key not in self._pending_file_reports:
            return False

        if not text:
            return False

        trigger_exact = {"要", "好的", "行", "可以", "发", "嗯"}
        trigger_prefix = ("详细", "完整", "报告", "发一下", "发给我")
        text_stripped = text.strip()
        if not (text_stripped in trigger_exact or any(text_stripped.startswith(w) for w in trigger_prefix)):
            del self._pending_file_reports[pending_key]
            return False

        pending = self._pending_file_reports.pop(pending_key)
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

    _MENU_NUMBER_MAP = {"1": 0, "2": 1, "3": 2, "4": 3, "5": 4, "6": 5,
                        "①": 0, "②": 1, "③": 2, "④": 3, "⑤": 4, "⑥": 5,
                        "一": 0, "二": 1, "三": 2, "四": 3, "五": 4, "六": 5}

    _MENU_TYPE_NAMES = [
        "快速简报", "标准投资报告", "深度研报",
        "景气度跟踪", "投委会备忘录", "公司速览",
    ]

    _MENU_SELECTION_PATTERNS = [
        (r"选\s*([1-6①-⑥一二三四五六])", 1),
        (r"第\s*([1-6①-⑥一二三四五六])\s*个", 1),
        (r"我要\s*([1-6①-⑥一二三四五六])", 1),
        (r"([1-6①-⑥一二三四五六])\s*号", 1),
    ]

    def _check_menu_selection(self, from_user: str, text: str) -> Optional[dict]:
        if not text:
            return None
        mem_key = self._memory_key(from_user)
        with self._pending_skill_menus_lock:
            pending = self._pending_skill_menus.get(mem_key)
            if not pending:
                return None
            if time.time() - pending["timestamp"] > 300:
                del self._pending_skill_menus[mem_key]
                return None

        text_stripped = text.strip()
        report_type = None
        selected_idx = None

        if text_stripped in self._MENU_NUMBER_MAP:
            selected_idx = self._MENU_NUMBER_MAP[text_stripped]
        else:
            for pattern, group_idx in self._MENU_SELECTION_PATTERNS:
                match = re.search(pattern, text_stripped)
                if match:
                    num_str = match.group(group_idx)
                    if num_str in self._MENU_NUMBER_MAP:
                        selected_idx = self._MENU_NUMBER_MAP[num_str]
                        break

        if selected_idx is not None and selected_idx < len(self._MENU_TYPE_NAMES):
            report_type = self._MENU_TYPE_NAMES[selected_idx]

        if not report_type:
            skill = pending["skill"]
            report_type = self._match_menu_keyword(text, skill)

        result = None
        if report_type:
            result = {
                "report_type": report_type,
                "original_text": pending.get("original_text", ""),
                "file_contexts": pending.get("file_contexts", []),
                "skill": pending.get("skill"),
            }
            with self._pending_skill_menus_lock:
                self._pending_skill_menus.pop(mem_key, None)

        return result

    def _resolve_skill_menus(self, selected_skills, from_user: str, text: str, file_contexts: list, context_token: str, skill_context: str, skip_menu: bool = False) -> Optional[str]:
        for skill in selected_skills:
            if skill.menu:
                if skip_menu:
                    skill_context += "\n\n用户已选择报告类型：快速简报。请直接按此类型输出，不要再询问。"
                else:
                    report_type = self._get_selected_report_type(from_user)
                    if report_type:
                        skill_context += f"\n\n用户已选择报告类型：{report_type}。请直接按此类型输出，不要再询问。"
                    else:
                        keyword_type = self._match_menu_keyword(text, skill)
                        if keyword_type:
                            skill_context += f"\n\n用户已选择报告类型：{keyword_type}。请直接按此类型输出，不要再询问。"
                        else:
                            self.ilink.send_message(skill.menu, from_user, context_token)
                            self._set_pending_menu(from_user, skill, text, file_contexts)
                            self.logger.info(f"sent skill menu to {from_user}: {skill.name}")
                            return None
        return skill_context

    def _match_menu_keyword(self, text: str, skill) -> Optional[str]:
        if not text or not skill.menu_keywords:
            return None
        text_lower = text.lower()
        for mapping in skill.menu_keywords:
            if "=" not in mapping:
                continue
            keyword, report_type = mapping.split("=", 1)
            if keyword.strip().lower() in text_lower:
                return report_type.strip()
        return None

    def _set_pending_menu(self, from_user: str, skill, original_text: str, file_contexts: list) -> None:
        mem_key = self._memory_key(from_user)
        with self._pending_skill_menus_lock:
            self._pending_skill_menus[mem_key] = {
                "skill": skill,
                "timestamp": time.time(),
                "original_text": original_text,
                "file_contexts": file_contexts,
            }

    def _set_selected_report_type(self, from_user: str, report_type: str) -> None:
        mem_key = self._memory_key(from_user)
        self._selected_report_types[mem_key] = (report_type, time.time())

    def _get_selected_report_type(self, from_user: str) -> Optional[str]:
        mem_key = self._memory_key(from_user)
        entry = self._selected_report_types.get(mem_key)
        if not entry:
            return None
        report_type, ts = entry
        if time.time() - ts > self._report_type_ttl:
            self._selected_report_types.pop(mem_key, None)
            return None
        return self._selected_report_types.pop(mem_key)[0]

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
        self.logger.info(f"detected video URL in text: {url[:80]}...")
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
            return f"{self.account_id}:{from_user}:{msg_id}"
        text_parts = []
        for item in msg.get("item_list", []):
            if item.get("type") == 1:
                text_parts.append(item.get("text_item", {}).get("text", ""))
        raw = f"{self.account_id}:{from_user}:{':'.join(text_parts)}:{msg.get('context_token', '')[:20]}"
        return hashlib.md5(raw.encode("utf-8")).hexdigest()

    def _is_duplicate(self, msg_id: str) -> bool:
        with self._seen_msgs_lock:
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

    def _content_fingerprint(self, msg: dict) -> str:
        from_user = msg.get("from_user_id", "")
        parts = [from_user]
        has_media = False
        for item in msg.get("item_list", []):
            item_type = item.get("type")
            if item_type == 1:
                continue
            has_media = True
            image_item = item.get("image_item", {})
            video_item = item.get("video_item", {})
            audio_item = item.get("audio_item", {}) or item.get("voice_item", {})
            media = image_item.get("media", {}) or video_item.get("media", {}) or audio_item.get("media", {})
            aes_key = media.get("aes_key", "")
            url = media.get("full_url", "") or media.get("url", "")
            parts.append(f"{item_type}:{aes_key}:{url}")
        if not has_media:
            return ""
        raw = f"{self.account_id}:{':'.join(parts)}"
        return hashlib.md5(raw.encode("utf-8")).hexdigest()

    def _is_content_duplicate(self, fp: str) -> bool:
        with self._content_fp_lock:
            now = time.time()
            if fp in self._content_fingerprints:
                return True
            self._content_fingerprints[fp] = now
            expired = [k for k, ts in self._content_fingerprints.items() if now - ts > self._content_fp_ttl]
            for k in expired:
                del self._content_fingerprints[k]
            return False


SESSIONS_DIR = Path("sessions")


class BotManager:
    def __init__(self):
        self.bots: dict[str, WeChatBot] = {}
        self._running = False
        self.logger = logging.getLogger("manager")

    def add_account(self) -> bool:
        SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
        temp_path = SESSIONS_DIR / f"_pending_{uuid.uuid4().hex[:8]}.json"
        client = ILinkClient(config_path=str(temp_path))
        print("\n=== 添加新账号 ===")
        print("请用微信扫描二维码：\n")
        try:
            success = client.login()
        except Exception as e:
            self.logger.error(f"login failed: {e}")
            success = False
        if success:
            account_id = client.bot_id or uuid.uuid4().hex[:8]
            final_path = SESSIONS_DIR / f"{account_id}.json"
            if temp_path.exists():
                temp_path.rename(final_path)
            print(f"\n账号添加成功！ID: {account_id}")
            self.logger.info(f"new account added: {account_id}")
        else:
            if temp_path.exists():
                temp_path.unlink()
            print("\n账号添加失败")
        return success

    def list_accounts(self):
        if not SESSIONS_DIR.exists():
            print("暂无已配置的账号。使用 --add 添加新账号。")
            return
        sessions = list(SESSIONS_DIR.glob("*.json"))
        if not sessions:
            print("暂无已配置的账号。使用 --add 添加新账号。")
            return
        print(f"\n已配置 {len(sessions)} 个账号：")
        print("-" * 50)
        for session_file in sorted(sessions):
            account_id = session_file.stem
            try:
                data = json.loads(session_file.read_text())
                bot_id = data.get("ilink_bot_id", "unknown")
                user_id = data.get("ilink_user_id", "unknown")
                has_token = bool(data.get("bot_token"))
                status = "已登录" if has_token else "需要重新扫码"
                print(f"  账号: {account_id}")
                print(f"  状态: {status}")
                print(f"  Bot ID: {bot_id}")
                print(f"  User ID: {user_id}")
                print("-" * 50)
            except Exception as e:
                print(f"  账号: {account_id} (读取失败: {e})")
                print("-" * 50)

    def remove_account(self, account_id: str):
        session_path = SESSIONS_DIR / f"{account_id}.json"
        if not session_path.exists():
            print(f"账号 {account_id} 不存在")
            return
        session_path.unlink()
        print(f"账号 {account_id} 已移除")
        self.logger.info(f"account removed: {account_id}")

    def start(self):
        accounts = self._discover_accounts()
        if not accounts:
            self.logger.info("no multi-account sessions found, falling back to single-account mode")
            bot = WeChatBot()
            bot.start()
            return

        shared = self._create_shared()
        for account_id, session_path in accounts:
            bot = WeChatBot(session_path=str(session_path), shared=shared)
            self.bots[account_id] = bot

        self.logger.info(f"starting {len(self.bots)} account(s): {list(self.bots.keys())}")

        self._running = True

        def _shutdown(sig, frame):
            self.logger.info("manager received shutdown signal")
            self._running = False
            for bot in self.bots.values():
                bot._running = False
                try:
                    bot.ilink.notify_stop()
                except Exception:
                    pass

        signal.signal(signal.SIGINT, _shutdown)
        signal.signal(signal.SIGTERM, _shutdown)

        threads = []
        for account_id, bot in self.bots.items():
            t = threading.Thread(target=self._run_bot, args=(account_id, bot), daemon=True)
            t.start()
            threads.append(t)
            self.logger.info(f"thread started for account: {account_id}")

        try:
            while self._running:
                alive = [t for t in threads if t.is_alive()]
                if not alive:
                    self.logger.info("all bot threads stopped")
                    break
                time.sleep(1)
        except KeyboardInterrupt:
            self.logger.info("keyboard interrupt, shutting down...")
            self._running = False
            for bot in self.bots.values():
                bot._running = False

        for t in threads:
            t.join(timeout=10)
        cleanup_pid_file()
        self.logger.info("manager shutdown complete")

    def _discover_accounts(self) -> list[tuple[str, Path]]:
        if not SESSIONS_DIR.exists():
            return []
        accounts = []
        for session_file in sorted(SESSIONS_DIR.glob("*.json")):
            if session_file.stem.startswith("_"):
                continue
            accounts.append((session_file.stem, session_file))
        return accounts

    def _create_shared(self) -> dict:
        config = WeChatBot._load_config_static()
        parser = MessageParser()
        file_cfg = config.get("files", {})
        max_upload_mb = file_cfg.get("max_upload_mb", 200)
        context_tokens = config.get("llm", {}).get("context_window_tokens", 1000000)
        reserved_tokens = file_cfg.get("reserved_prompt_tokens", 150000)
        max_file_tokens = file_cfg.get("max_file_tokens", max(1000, context_tokens - reserved_tokens))
        attachments = AttachmentStore(
            max_file_bytes=max_upload_mb * 1024 * 1024,
            retention_days=file_cfg.get("upload_retention_days", 30),
        )
        documents = DocumentAnalyzer(
            max_file_tokens=max_file_tokens,
            multimodal=config.get("multimodal", {}),
        )
        memory_cfg = config.get("memory", {})
        memory = MemoryStore(
            base_dir=memory_cfg.get("base_dir", "data/memory"),
            max_recent_turns=memory_cfg.get("max_recent_turns", 8),
            max_active_files=memory_cfg.get("max_active_files", 3),
            max_relevant_chunks=memory_cfg.get("max_relevant_chunks", 5),
            max_summary_chars=memory_cfg.get("max_summary_chars", 6000),
        )
        llm = LLMEngine(memory_store=memory)
        skill_cfg = config.get("skills", {})
        skills = SkillRuntime(
            skill_dirs=skill_cfg.get("dirs", ["skills", "user_skills"]),
            max_loaded_skills=skill_cfg.get("max_loaded_skills", 2),
        )
        reply_cfg = config.get("reply", {})
        return {
            "parser": parser,
            "attachments": attachments,
            "documents": documents,
            "memory": memory,
            "llm": llm,
            "skills": skills,
            "max_total_file_tokens": file_cfg.get("max_total_file_tokens", max_file_tokens),
            "large_file_strategy": file_cfg.get("large_file_strategy", "chunk_summary"),
            "max_chat_chars": reply_cfg.get("max_chat_chars", 800),
            "auto_split_threshold": reply_cfg.get("auto_split_threshold", 2000),
            "file_output_threshold": reply_cfg.get("file_output_threshold", 3000),
            "split_delay": reply_cfg.get("split_delay_seconds", 0.5),
            "seen_msgs": OrderedDict(),
            "seen_msgs_lock": threading.Lock(),
            "content_fingerprints": {},
            "content_fp_lock": threading.Lock(),
        }

    def _run_bot(self, account_id: str, bot: WeChatBot):
        try:
            if not bot.ilink.token:
                self.logger.info(f"[{account_id}] no saved session, need QR login...")
                if not bot.ilink.login():
                    self.logger.error(f"[{account_id}] QR login failed, skipping")
                    return
            bot._run()
        except Exception as e:
            self.logger.error(f"[{account_id}] bot error: {e}", exc_info=True)


if __name__ == "__main__":
    loaded_keys, skipped_keys = _load_dotenv()
    if loaded_keys:
        logger.info(f".env 加载了 {len(loaded_keys)} 个变量: {', '.join(loaded_keys)}")
    if skipped_keys:
        logger.info(f".env 跳过了 {len(skipped_keys)} 个已存在的变量: {', '.join(skipped_keys)}")

    arg_parser = argparse.ArgumentParser(
        description="WePilot - 微信智能助手",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python3 bot.py              启动机器人（单账号或多账号）
  python3 bot.py --add        添加新微信账号（扫码）
  python3 bot.py --list       查看已配置的账号
  python3 bot.py --remove ID  移除指定账号
        """,
    )
    arg_parser.add_argument("--add", action="store_true", help="添加新的微信账号（扫描二维码）")
    arg_parser.add_argument("--list", action="store_true", help="列出所有已配置的账号")
    arg_parser.add_argument("--remove", metavar="ACCOUNT_ID", help="移除指定账号")
    args = arg_parser.parse_args()

    manager = BotManager()

    if args.list:
        manager.list_accounts()
    elif args.remove:
        manager.remove_account(args.remove)
    elif args.add:
        manager.add_account()
    else:
        if not check_single_instance():
            sys.exit(1)
        try:
            manager.start()
        finally:
            cleanup_pid_file()
