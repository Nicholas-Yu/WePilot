import base64
import json
import logging
import os
import random
import time
import uuid
from collections import OrderedDict
from pathlib import Path

import httpx

logger = logging.getLogger("ilink")

ILINK_BASE = "https://ilinkai.weixin.qq.com"


class ILinkClient:
    def __init__(self, config_path: str = "session.json", channel_version: str = "2.1.10"):
        self.base = ILINK_BASE
        self.token: str = ""
        self.bot_id: str = ""
        self.user_id: str = ""
        self.api_base_url: str = ILINK_BASE
        self._cursor: str = ""
        self._context_tokens: OrderedDict[str, str] = OrderedDict()
        self._context_tokens_max = 200
        self.config_path = Path(config_path)
        self.channel_version = channel_version

        self._load_session()

    def _load_session(self):
        if self.config_path.exists():
            try:
                cfg = json.loads(self.config_path.read_text())
                self.token = cfg.get("bot_token", "")
                self.bot_id = cfg.get("ilink_bot_id", "")
                self.user_id = cfg.get("ilink_user_id", "")
                self.api_base_url = cfg.get("api_base_url", ILINK_BASE)
                self._cursor = cfg.get("cursor", "")
                self._context_tokens = OrderedDict(cfg.get("context_tokens", {}))
                logger.info(f"session loaded: bot_id={self.bot_id}")
            except Exception as e:
                logger.warning(f"session load failed: {e}")

        self.token = os.environ.get("ILINK_BOT_TOKEN", self.token)
        self.bot_id = os.environ.get("ILINK_BOT_ID", self.bot_id)
        self.user_id = os.environ.get("ILINK_USER_ID", self.user_id)
        api_base = os.environ.get("ILINK_API_BASE_URL")
        if api_base:
            self.api_base_url = api_base

    def _save_session(self):
        try:
            cfg = {
                "bot_token": self.token,
                "ilink_bot_id": self.bot_id,
                "ilink_user_id": self.user_id,
                "api_base_url": self.api_base_url,
                "cursor": self._cursor,
                "context_tokens": self._context_tokens,
            }
            self.config_path.write_text(json.dumps(cfg, indent=2, ensure_ascii=False))
        except Exception as e:
            logger.warning(f"session save failed: {e}")

    def _build_client_version(self) -> int:
        parts = self.channel_version.split(".")
        major = int(parts[0]) if len(parts) > 0 else 0
        minor = int(parts[1]) if len(parts) > 1 else 0
        patch = int(parts[2]) if len(parts) > 2 else 0
        return ((major & 0xFF) << 16) | ((minor & 0xFF) << 8) | (patch & 0xFF)

    def _random_wechat_uin(self) -> str:
        uint32 = random.randint(0, 0xFFFFFFFF)
        return base64.b64encode(str(uint32).encode()).decode()

    def _common_headers(self) -> dict[str, str]:
        return {
            "iLink-App-Id": "bot",
            "iLink-App-ClientVersion": str(self._build_client_version()),
        }

    def _post_headers(self, body: str) -> dict[str, str]:
        headers = {
            "Content-Type": "application/json",
            "AuthorizationType": "ilink_bot_token",
            "Authorization": f"Bearer {self.token}",
            "Content-Length": str(len(body.encode("utf-8"))),
            "X-WECHAT-UIN": self._random_wechat_uin(),
        }
        headers.update(self._common_headers())
        return headers

    def _get_headers(self) -> dict[str, str]:
        return self._common_headers()

    def absolute_url(self, url: str) -> str:
        if url.startswith("http://") or url.startswith("https://"):
            return url
        if url.startswith("/"):
            return f"{self.api_base_url}{url}"
        return f"{self.api_base_url}/{url}"

    def download_headers(self) -> dict[str, str]:
        headers = {
            "AuthorizationType": "ilink_bot_token",
            "Authorization": f"Bearer {self.token}",
            "X-WECHAT-UIN": self._random_wechat_uin(),
        }
        headers.update(self._common_headers())
        return headers

    def _post(self, endpoint: str, body: dict, timeout: float = 35) -> dict:
        payload = dict(body)
        payload["base_info"] = {"channel_version": self.channel_version}
        raw = json.dumps(payload, ensure_ascii=False)
        headers = self._post_headers(raw)
        url = f"{self.api_base_url}/ilink/bot/{endpoint}"
        try:
            resp = httpx.post(url, content=raw.encode("utf-8"), headers=headers, timeout=timeout)
            text = resp.text.strip()
            if text and text != "{}":
                return json.loads(text)
            return {"ret": 0}
        except httpx.TimeoutException:
            logger.debug(f"{endpoint}: timeout, returning empty")
            return {"ret": 0}
        except Exception as e:
            logger.error(f"{endpoint}: error {e}")
            raise

    def _get(self, endpoint: str, timeout: float = 40) -> dict:
        url = self.absolute_url(endpoint)
        headers = self._get_headers()
        try:
            resp = httpx.get(url, headers=headers, timeout=timeout)
            return resp.json()
        except httpx.TimeoutException:
            logger.debug(f"GET {endpoint}: timeout")
            return {"status": "wait"}
        except Exception as e:
            logger.error(f"GET {endpoint}: error {e}")
            raise

    def login_qr(self) -> dict:
        resp = self._get("ilink/bot/get_bot_qrcode?bot_type=3")
        return {
            "qrcode_key": resp.get("qrcode", ""),
            "qrcode_url": resp.get("qrcode_img_content", ""),
        }

    def poll_qr_status(self, qrcode_key: str) -> dict:
        endpoint = f"ilink/bot/get_qrcode_status?qrcode={qrcode_key}"
        return self._get(endpoint)

    def login(self, timeout: int = 300) -> bool:
        logger.info("starting QR login...")
        qr = self.login_qr()
        qrcode_key = qr["qrcode_key"]
        qrcode_url = qr["qrcode_url"]

        if not qrcode_url:
            logger.error("failed to get QR code")
            return False

        print("\n请用微信扫描以下二维码：")
        print(f"链接：{qrcode_url}\n")

        try:
            import qrcode
            qr_img = qrcode.QRCode(border=1)
            qr_img.add_data(qrcode_url)
            qr_img.make(fit=True)
            qr_img.print_ascii(invert=True)
        except ImportError:
            print("(安装 qrcode 库可显示终端二维码: pip install qrcode)")

        start_time = time.time()
        while True:
            elapsed = time.time() - start_time
            if elapsed > timeout:
                logger.error(f"QR login timed out after {timeout}s")
                print(f"\n登录超时（{timeout // 60} 分钟），请重试。")
                return False

            status = self.poll_qr_status(qrcode_key)
            s = status.get("status", "wait")

            if s == "scaned":
                print("已扫码，请在手机上确认...")
            elif s == "confirmed":
                self.token = status.get("bot_token", "")
                self.bot_id = status.get("ilink_bot_id", "")
                self.user_id = status.get("ilink_user_id", "")
                base_url = status.get("baseurl", "")
                if base_url:
                    self.api_base_url = f"https://{base_url}" if not base_url.startswith("https") else base_url
                self._save_session()
                print(f"\n登录成功！bot_id={self.bot_id}")
                return True
            elif s == "expired":
                print("二维码过期，重新获取...")
                qr = self.login_qr()
                qrcode_key = qr["qrcode_key"]
                qrcode_url = qr["qrcode_url"]
                if not qrcode_url:
                    logger.error("failed to refresh QR code")
                    return False
                print(f"\n新二维码链接：{qrcode_url}\n")
                start_time = time.time()
            elif s == "scaned_but_redirect":
                redirect_host = status.get("redirect_host", "")
                if redirect_host:
                    self.api_base_url = f"https://{redirect_host}"
                    logger.info(f"IDC redirect to {redirect_host}")
            elif s == "wait":
                pass
            else:
                logger.warning(f"unknown status: {s}")

            time.sleep(1)

    def get_updates(self) -> list[dict]:
        result = self._post("getupdates", {"get_updates_buf": self._cursor})
        self._cursor = result.get("get_updates_buf", self._cursor)
        msgs = result.get("msgs", [])
        for msg in msgs:
            ct = msg.get("context_token", "")
            from_user = msg.get("from_user_id", "")
            if ct and from_user:
                if from_user in self._context_tokens:
                    self._context_tokens.move_to_end(from_user)
                self._context_tokens[from_user] = ct
                while len(self._context_tokens) > self._context_tokens_max:
                    self._context_tokens.popitem(last=False)
        if msgs or self._cursor:
            self._save_session()
        return msgs

    def send_message(self, text: str, to_user_id: str, context_token: str = "") -> bool:
        ct = context_token or self._context_tokens.get(to_user_id, "")
        if not ct:
            logger.warning(f"no context_token for {to_user_id}, message may not be delivered")

        body = {
            "msg": {
                "from_user_id": "",
                "to_user_id": to_user_id,
                "client_id": f"bot-{uuid.uuid4().hex[:12]}",
                "message_type": 2,
                "message_state": 2,
                "context_token": ct,
                "item_list": [{"type": 1, "text_item": {"text": text}}],
            }
        }
        try:
            self._post("sendmessage", body, timeout=15)
            return True
        except Exception as e:
            logger.error(f"send failed: {e}")
            return False

    def notify_start(self) -> dict:
        return self._post("msg/notifystart", {})

    def notify_stop(self) -> dict:
        return self._post("msg/notifystop", {})

    def get_config(self, ilink_user_id: str, context_token: str = "") -> dict:
        return self._post("getconfig", {
            "ilink_user_id": ilink_user_id,
            "context_token": context_token,
        })

    def send_typing(self, ilink_user_id: str, typing_ticket: str) -> dict:
        return self._post("sendtyping", {
            "ilink_user_id": ilink_user_id,
            "typing_ticket": typing_ticket,
            "status": 1,
        })

    def extract_text(self, msg: dict) -> str:
        text = ""
        for item in msg.get("item_list", []):
            if item.get("type") == 1:
                text += item.get("text_item", {}).get("text", "")
        return text
