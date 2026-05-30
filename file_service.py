import base64
import hashlib
import logging
import re
import time
from pathlib import Path
from typing import Any, Optional

import httpx

from message_parser import Attachment
import replies

logger = logging.getLogger("files")


class AttachmentStore:
    def __init__(self, base_dir: str = "data/uploads", max_file_bytes: int = 20 * 1024 * 1024, retention_days: int = 30):
        self.base_dir = Path(base_dir)
        self.max_file_bytes = max_file_bytes
        self.retention_days = retention_days

    def materialize(self, user_id: str, attachment: Attachment, ilink_client: Any) -> Optional[Path]:
        if attachment.size and attachment.size > self.max_file_bytes:
            logger.warning("attachment too large: %s bytes", attachment.size)
            raise ValueError(replies.UPLOAD_TOO_LARGE.format(
                size=attachment.size / 1024 / 1024,
                limit=self.max_file_bytes / 1024 / 1024,
            ))

        target = self._target_path(user_id, attachment)

        inline = self._inline_bytes(attachment.raw_item)
        if inline:
            if len(inline) > self.max_file_bytes:
                logger.warning("inline attachment too large: %s bytes", len(inline))
                return None
            target.write_bytes(inline)
            self._decrypt_if_needed(target, attachment)
            return target

        if attachment.url:
            return self._download_url(attachment.url, target, attachment, ilink_client)

        logger.info("attachment has no inline data or url; item_type=%s file_id=%s", attachment.item_type, attachment.file_id)
        return None

    def _target_path(self, user_id: str, attachment: Attachment) -> Path:
        date = time.strftime("%Y%m%d")
        safe_user = self._safe_name(user_id or "unknown")
        filename = attachment.filename or self._fallback_name(attachment)
        target_dir = self.base_dir / safe_user / date
        target_dir.mkdir(parents=True, exist_ok=True)
        return target_dir / self._safe_name(filename)

    def _fallback_name(self, attachment: Attachment) -> str:
        seed = attachment.file_id or attachment.url or repr(attachment.raw_item)
        digest = hashlib.sha256(seed.encode("utf-8", errors="ignore")).hexdigest()[:12]
        ext = ".bin"
        mime = attachment.mime_type.lower()
        if mime.startswith("image/"):
            ext = ".jpg" if mime == "image/jpeg" else f".{mime.split('/')[-1]}"
        elif mime.startswith("video/"):
            ext = f".{mime.split('/')[-1]}"
        elif mime.startswith("audio/"):
            ext = f".{mime.split('/')[-1]}"
        return f"attachment-{attachment.item_type}-{digest}{ext}"

    def _safe_name(self, value: str) -> str:
        value = value.strip().replace("/", "_").replace("\\", "_")
        value = re.sub(r"[\x00-\x1f:<>\"|?*]+", "_", value)
        return value[:160] or "attachment.bin"

    def _download_url(self, url: str, target: Path, attachment: Attachment, ilink_client: Any) -> Optional[Path]:
        absolute_url = ilink_client.absolute_url(url)
        headers = ilink_client.download_headers()
        with httpx.stream("GET", absolute_url, headers=headers, timeout=60) as response:
            response.raise_for_status()
            total = 0
            with target.open("wb") as fh:
                for chunk in response.iter_bytes():
                    total += len(chunk)
                    if total > self.max_file_bytes:
                        target.unlink(missing_ok=True)
                        logger.warning("downloaded attachment too large: %s bytes", total)
                        return None
                    fh.write(chunk)
        self._decrypt_if_needed(target, attachment)
        return target

    def _decrypt_if_needed(self, path: Path, attachment: Attachment) -> None:
        if not attachment.file_id:
            logger.info(f"no file_id for {path.name}, skipping decryption")
            return

        raw = path.read_bytes()
        if self._looks_plain(raw):
            logger.info(f"file {path.name} looks plain, no decryption needed")
            return

        logger.info(f"file {path.name} is encrypted, attempting decryption with file_id={attachment.file_id[:20]}...")
        key = self._wechat_aes_key(attachment.file_id)
        if not key:
            logger.warning(f"failed to derive AES key from file_id for {path.name}")
            return

        try:
            from Crypto.Cipher import AES
        except ImportError:
            logger.warning("pycryptodome is not installed; cannot decrypt attachment")
            return

        encrypted = raw[: len(raw) - (len(raw) % 16)]
        candidates = [
            AES.new(key, AES.MODE_ECB).decrypt(encrypted),
            AES.new(key, AES.MODE_CBC, iv=b"\x00" * 16).decrypt(encrypted),
        ]
        for decrypted in candidates:
            if attachment.size and len(decrypted) > attachment.size:
                decrypted = decrypted[: attachment.size]
            else:
                decrypted = self._unpad_pkcs7(decrypted)
            if self._looks_plain(decrypted):
                path.write_bytes(decrypted)
                logger.info("decrypted attachment: %s", path.name)
                return
        logger.warning(f"decryption failed for {path.name}, file remains encrypted")

    def _wechat_aes_key(self, value: str) -> bytes:
        try:
            decoded = base64.b64decode(value).decode("ascii")
            return bytes.fromhex(decoded)
        except Exception:
            return b""

    def _unpad_pkcs7(self, data: bytes) -> bytes:
        if not data:
            return data
        pad = data[-1]
        if 1 <= pad <= 16 and data.endswith(bytes([pad]) * pad):
            return data[:-pad]
        return data

    def _looks_plain(self, data: bytes) -> bool:
        if len(data) < 8:
            return False
        return (
            data.startswith(b"PK\x03\x04")
            or data.startswith(b"%PDF")
            or data.startswith(b"\xef\xbb\xbf")
            or data.startswith(b"\xff\xd8\xff")
            or data.startswith(b"\x89PNG")
            or data.startswith(b"GIF8")
            or data.startswith(b"RIFF")
            or data.startswith(b"BM")
            or data.startswith(b"\x1a\x45\xdf\xa3")
            or data[4:8] in (b"ftyp", b"moov", b"mdat", b"free", b"wide", b"skip")
            or data[:256].lstrip().startswith((b"{", b"[", b"<", b"#"))
        )

    def _inline_bytes(self, obj: Any) -> bytes:
        for key, value in self._walk(obj):
            if not isinstance(value, str):
                continue
            if key in ("content", "data", "file_content", "bytes", "base64"):
                decoded = self._try_b64decode(value)
                if decoded:
                    return decoded
        return b""

    def _try_b64decode(self, value: str) -> bytes:
        text = value.strip()
        if "," in text and text[:32].lower().startswith("data:"):
            text = text.split(",", 1)[1]
        if len(text) < 16:
            return b""
        try:
            return base64.b64decode(text, validate=True)
        except Exception:
            return b""

    def _walk(self, obj: Any):
        if isinstance(obj, dict):
            for key, value in obj.items():
                yield key, value
                yield from self._walk(value)
        elif isinstance(obj, list):
            for value in obj:
                yield from self._walk(value)

    def cleanup_expired(self) -> int:
        if self.retention_days <= 0:
            return 0
        if not self.base_dir.exists():
            return 0
        cutoff = time.time() - self.retention_days * 86400
        removed = 0
        for file_path in self.base_dir.rglob("*"):
            if not file_path.is_file():
                continue
            if file_path.stat().st_mtime < cutoff:
                try:
                    file_path.unlink()
                    removed += 1
                except Exception as e:
                    logger.warning(f"failed to remove expired file {file_path}: {e}")
        for dir_path in sorted(self.base_dir.rglob("*"), reverse=True):
            if dir_path.is_dir() and not any(dir_path.iterdir()):
                try:
                    dir_path.rmdir()
                except Exception:
                    pass
        if removed:
            logger.info(f"cleaned up {removed} expired upload files (>{self.retention_days} days)")
        return removed
