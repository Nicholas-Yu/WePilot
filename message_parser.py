import json
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


logger = logging.getLogger("parser")

TEXT_ITEM_TYPE = 1


@dataclass
class Attachment:
    item_type: int
    filename: str = ""
    mime_type: str = ""
    size: int = 0
    url: str = ""
    file_id: str = ""
    raw_item: dict[str, Any] = field(default_factory=dict)
    is_quoted: bool = False


@dataclass
class ParsedMessage:
    user_id: str
    context_token: str
    text: str
    attachments: list[Attachment] = field(default_factory=list)
    quoted_text: str = ""
    quoted_timestamp: int = 0
    raw: dict[str, Any] = field(default_factory=dict)


class MessageParser:
    def parse(self, msg: dict[str, Any]) -> ParsedMessage:
        return ParsedMessage(
            user_id=msg.get("from_user_id", ""),
            context_token=msg.get("context_token", ""),
            text=self.extract_text(msg),
            attachments=self.extract_attachments(msg),
            quoted_text=self.extract_quoted_text(msg),
            quoted_timestamp=self.extract_quoted_timestamp(msg),
            raw=msg,
        )

    def extract_text(self, msg: dict[str, Any]) -> str:
        parts = []
        for item in msg.get("item_list", []):
            if item.get("type") == TEXT_ITEM_TYPE:
                text = item.get("text_item", {}).get("text", "")
                if text:
                    parts.append(text)
        return "".join(parts).strip()

    def extract_quoted_text(self, msg: dict[str, Any]) -> str:
        parts = []
        for item in msg.get("item_list", []):
            ref_msg = item.get("ref_msg")
            if not ref_msg:
                continue
            title = ref_msg.get("title", "")
            if title:
                parts.append(title)
            ref_item = ref_msg.get("message_item", {})
            if ref_item.get("type") == TEXT_ITEM_TYPE:
                text = ref_item.get("text_item", {}).get("text", "")
                if text:
                    parts.append(text)
        return "\n".join(parts).strip()

    def extract_quoted_timestamp(self, msg: dict[str, Any]) -> int:
        for item in msg.get("item_list", []):
            ref_msg = item.get("ref_msg")
            if not ref_msg:
                continue
            ref_item = ref_msg.get("message_item", {})
            ts = ref_item.get("create_time_ms", 0)
            if ts:
                return int(ts)
        return 0

    def extract_attachments(self, msg: dict[str, Any]) -> list[Attachment]:
        attachments = []
        for item in msg.get("item_list", []):
            item_type = item.get("type")
            if item_type != TEXT_ITEM_TYPE:
                attachments.append(self._attachment_from_item(item))

            ref_msg = item.get("ref_msg")
            if ref_msg:
                ref_item = ref_msg.get("message_item", {})
                ref_type = ref_item.get("type")
                if ref_type and ref_type != TEXT_ITEM_TYPE:
                    logger.info(f"found quoted message: type={ref_type}, title={repr(ref_msg.get('title', ''))[:50]}")
                    logger.info(f"quoted item keys: {list(ref_item.keys())}")
                    if ref_item.get("image_item"):
                        logger.info(f"quoted image_item present")
                    if ref_item.get("video_item"):
                        logger.info(f"quoted video_item present")
                    att = self._attachment_from_item(ref_item)
                    att.is_quoted = True
                    attachments.append(att)
                elif ref_msg.get("title"):
                    logger.info(f"found quoted text message: title={repr(ref_msg.get('title', ''))[:50]}")
                else:
                    logger.info(f"found quoted message without title: ref_item={ref_item}")
        return attachments

    def save_debug_message(self, msg: dict[str, Any], debug_dir: Path, reason: str) -> Path:
        debug_dir.mkdir(parents=True, exist_ok=True)
        msg_id = msg.get("msg_id") or msg.get("client_id") or "message"
        safe_id = re.sub(r"[^a-zA-Z0-9_.-]+", "_", str(msg_id))[:80]
        path = debug_dir / f"{int(__import__('time').time())}_{safe_id}.json"
        payload = {
            "reason": reason,
            "message": self._redact_sensitive(msg),
        }
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return path

    def _attachment_from_item(self, item: dict[str, Any]) -> Attachment:
        item_type = int(item.get("type") or 0)

        image_item = item.get("image_item")
        if image_item:
            media = image_item.get("media", {})
            aes_key_b64 = media.get("aes_key", "")
            url = media.get("full_url", "") or media.get("url", "")
            size = image_item.get("mid_size", 0) or image_item.get("thumb_size", 0)
            return Attachment(
                item_type=item_type,
                filename="",
                mime_type="image/jpeg",
                size=int(size) if size else 0,
                url=url,
                file_id=aes_key_b64,
                raw_item=item,
            )

        video_item = item.get("video_item")
        if video_item:
            media = video_item.get("media", {})
            aes_key_b64 = media.get("aes_key", "")
            url = media.get("full_url", "") or media.get("url", "")
            size = video_item.get("video_size", 0)
            return Attachment(
                item_type=item_type,
                filename="",
                mime_type="video/mp4",
                size=int(size) if size else 0,
                url=url,
                file_id=aes_key_b64,
                raw_item=item,
            )

        audio_item = item.get("audio_item") or item.get("voice_item")
        if audio_item:
            media = audio_item.get("media", {})
            aes_key_b64 = media.get("aes_key", "")
            url = media.get("full_url", "") or media.get("url", "")
            size = audio_item.get("audio_size", 0) or audio_item.get("voice_size", 0)
            return Attachment(
                item_type=item_type,
                filename="",
                mime_type="audio/mp3",
                size=int(size) if size else 0,
                url=url,
                file_id=aes_key_b64,
                raw_item=item,
            )

        return Attachment(
            item_type=item_type,
            filename=self._first_value(item, ("filename", "file_name", "name", "title")),
            mime_type=self._first_value(item, ("mime_type", "mimetype", "content_type")),
            size=self._first_int(item, ("size", "file_size", "length", "len")),
            url=self._first_value(item, ("download_url", "file_url", "full_url", "url", "cdn_url", "media_url")),
            file_id=self._first_value(item, ("file_id", "media_id", "id", "aes_key")),
            raw_item=item,
        )

    def _first_value(self, obj: Any, keys: tuple[str, ...]) -> str:
        for key, value in self._walk(obj):
            if key in keys and isinstance(value, str) and value.strip():
                return value.strip()
        return ""

    def _first_int(self, obj: Any, keys: tuple[str, ...]) -> int:
        for key, value in self._walk(obj):
            if key in keys:
                try:
                    return int(value)
                except (TypeError, ValueError):
                    return 0
        return 0

    def _walk(self, obj: Any):
        if isinstance(obj, dict):
            for key, value in obj.items():
                yield key, value
                yield from self._walk(value)
        elif isinstance(obj, list):
            for value in obj:
                yield from self._walk(value)

    def _redact_sensitive(self, obj: Any) -> Any:
        if isinstance(obj, dict):
            redacted = {}
            for key, value in obj.items():
                lower = key.lower()
                if "token" in lower or "ticket" in lower or "authorization" in lower:
                    redacted[key] = "[redacted]"
                else:
                    redacted[key] = self._redact_sensitive(value)
            return redacted
        if isinstance(obj, list):
            return [self._redact_sensitive(value) for value in obj]
        return obj
