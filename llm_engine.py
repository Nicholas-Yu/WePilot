import json
import logging
import math
import os
import time
from pathlib import Path
from typing import Any, Optional

from openai import OpenAI

import replies

logger = logging.getLogger("llm")

STYLE_PROMPTS = {
    "concise": "回复要简洁，尽量控制在3句话以内，不要长篇大论。",
    "detailed": "回复可以详细展开，给出充分的解释和例子。",
    "humorous": "回复要幽默有趣，适当使用轻松的语气和网络梗，但不要过度。",
}


class LLMEngine:
    def __init__(self, config_path: str = "config.json", memory_store=None):
        self.config_path = Path(config_path)
        self.memory = memory_store
        cfg = self._load_config()
        llm_cfg = cfg["llm"]

        self.client = OpenAI(
            base_url=os.environ.get("LLM_BASE_URL", llm_cfg.get("base_url", "")),
            api_key=os.environ.get("LLM_API_KEY", llm_cfg.get("api_key", "")),
            timeout=llm_cfg.get("request_timeout", 120),
            max_retries=llm_cfg.get("max_retries", 2),
        )
        self.model = os.environ.get("LLM_MODEL", llm_cfg.get("model", ""))
        self.bot_name = llm_cfg.get("bot_name", "AI助手")
        self.max_history = llm_cfg.get("max_history", 10)
        self.enable_search = llm_cfg.get("enable_search", False)
        self.temperature = llm_cfg.get("temperature", 0.7)
        self.top_p = llm_cfg.get("top_p")
        self.presence_penalty = llm_cfg.get("presence_penalty")
        self.frequency_penalty = llm_cfg.get("frequency_penalty")
        self.seed = llm_cfg.get("seed")
        self.max_tokens = llm_cfg.get("max_tokens", 512)
        self.reply_style = llm_cfg.get("reply_style", "concise")
        self.request_timeout = llm_cfg.get("request_timeout", 120)
        self.max_retries = llm_cfg.get("max_retries", 2)
        self.stream = llm_cfg.get("stream", False)
        self.include_usage = llm_cfg.get("include_usage", True)
        self.last_usage: dict[str, Any] = {}
        self.dashscope_extra_body = cfg.get("dashscope", {}).get("extra_body", {})
        self.task_profiles = cfg.get("task_profiles", {})
        file_cfg = cfg.get("files", {})
        self.chunk_tokens = file_cfg.get("chunk_tokens", 80000)
        self.chunk_summary_tokens = file_cfg.get("chunk_summary_tokens", 800)
        self.final_summary_tokens = file_cfg.get("final_summary_tokens", 1200)
        self.max_chunks = file_cfg.get("max_chunks", 24)
        self.multimodal = cfg.get("multimodal", {})
        self.system_prompt = self._build_system_prompt(cfg)
        self._histories: dict[str, list[dict]] = {}

    def _build_system_prompt(self, cfg: dict) -> str:
        custom_prompt = cfg.get("llm", {}).get("system_prompt", "")
        if custom_prompt:
            return custom_prompt

        name = self.bot_name
        style_hint = STYLE_PROMPTS.get(self.reply_style, STYLE_PROMPTS["concise"])
        search_hint = "你具备联网搜索能力，遇到需要查实时信息的问题（如天气、新闻、股价等）时，请主动搜索后再回答。" if self.enable_search else ""

        return (
            f"你的名字叫{name}，是一个微信AI助手。"
            f"当有人问你是谁、你叫什么名字时，你要回答「我叫{name}」。"
            f"{style_hint}"
            f"回复要自然口语化，像朋友聊天一样，不要用过于正式的语气。"
            f"{search_hint}"
            f"不要在回复中暴露你是AI或大模型，始终以{name}的身份回答。"
        )

    def _load_config(self) -> dict:
        if not self.config_path.exists():
            logger.error(f"config not found: {self.config_path}")
            logger.info("copy config.example.json to config.json and fill in your API key")
            raise FileNotFoundError(f"config not found: {self.config_path}")
        return json.loads(self.config_path.read_text())

    def _get_history(self, user_id: str) -> list[dict]:
        if user_id not in self._histories:
            if self.memory:
                self._histories[user_id] = self.memory.get_llm_history(user_id)
                if self._histories[user_id]:
                    logger.info(f"loaded {len(self._histories[user_id])} history messages for {user_id}")
            else:
                self._histories[user_id] = []
        return self._histories[user_id]

    def _trim_history(self, user_id: str):
        history = self._histories.get(user_id, [])
        if len(history) > self.max_history * 2:
            self._histories[user_id] = history[-(self.max_history * 2):]
        if self.memory:
            self.memory.save_llm_history(user_id, self._histories.get(user_id, []))

    def chat(
        self,
        user_id: str,
        user_message: str,
        files: Optional[list[Any]] = None,
        context_messages: Optional[list[dict[str, str]]] = None,
        record_history: bool = True,
    ) -> str:
        history = self._get_history(user_id)
        files = files or []
        content = self._build_user_content(user_message, files)

        if context_messages is None:
            context_messages = history

        messages = [{"role": "system", "content": self.system_prompt}] + context_messages + [{"role": "user", "content": content}]

        is_multimodal = isinstance(content, list)
        model_override = None
        use_streaming = False
        if is_multimodal:
            has_video_url = any(
                getattr(f, "source_url", "") and getattr(f, "mime_type", "").startswith("video/")
                for f in files
            )
            has_video_local = any(
                getattr(f, "base64_data", "") and getattr(f, "mime_type", "").startswith("video/")
                for f in files
            )
            has_audio = any(
                getattr(f, "base64_data", "") and getattr(f, "mime_type", "").startswith("audio/")
                for f in files
            )
            if has_video_url:
                video_url_model = self.multimodal.get("video_url_model", "")
                if video_url_model:
                    model_override = video_url_model
                    logger.info(f"switching to video URL model: {video_url_model}")
            elif has_video_local:
                video_model = self.multimodal.get("video_model", "")
                if video_model:
                    model_override = video_model
                    use_streaming = True
                    logger.info(f"switching to video model: {video_model}")
            elif has_audio:
                audio_model = self.multimodal.get("audio_model", "")
                if audio_model:
                    model_override = audio_model
                    use_streaming = True
                    logger.info(f"switching to audio model: {audio_model}")
            else:
                vision_model = self.multimodal.get("vision_model", "")
                if vision_model:
                    model_override = vision_model
                    logger.info(f"switching to vision model: {vision_model}")

        messages = self._merge_system_messages(messages)

        try:
            if use_streaming:
                reply = self._create_streaming_completion(messages, task="chat", model_override=model_override)
            else:
                response = self._create_chat_completion(messages, task="chat", model_override=model_override)
                reply = response.choices[0].message.content or ""
            if record_history:
                history.append({"role": "user", "content": self._build_history_user_content(user_message, files)})
                history.append({"role": "assistant", "content": reply})
                self._trim_history(user_id)
            return reply
        except Exception as e:
            logger.error(f"LLM call failed: {e}")
            return replies.LLM_ERROR

    def clear_history(self, user_id: str):
        self._histories.pop(user_id, None)
        if self.memory:
            self.memory.save_llm_history(user_id, [])

    def summarize_large_file(self, user_id: str, user_message: str, file_ctx: Any) -> Any:
        chunks = self._chunk_text(file_ctx.content, self.chunk_tokens)
        if len(chunks) > self.max_chunks:
            raise ValueError(f"文件需要分成 {len(chunks)} 块，超过当前上限 {self.max_chunks} 块。")

        chunk_summaries = []
        total = len(chunks)
        for index, chunk in enumerate(chunks, start=1):
            logger.info("summarizing chunk %s/%s for %s", index, total, file_ctx.filename)
            prompt = self._build_chunk_prompt(user_message, file_ctx, chunk, index, total)
            chunk_summaries.append(self._complete(prompt, task="chunk_summary", max_tokens=self.chunk_summary_tokens))

        final_prompt = self._build_final_summary_prompt(user_message, file_ctx, chunk_summaries)
        final_summary = self._complete(final_prompt, task="file_analysis", max_tokens=self.final_summary_tokens)
        file_ctx.content = final_summary
        file_ctx.error = f"文件较大，已分成 {total} 块摘要后再分析。"
        file_ctx.over_limit = False
        file_ctx.estimated_tokens = self._estimate_text_tokens(final_summary)
        file_ctx.chunk_summaries = chunk_summaries
        return file_ctx

    def summarize_file_for_memory(self, user_message: str, file_ctx: Any) -> Any:
        content = getattr(file_ctx, "content", "")
        if not content:
            return file_ctx
        prompt = (
            f"用户任务：{user_message.strip() or self._default_file_analysis_task()}\n"
            f"文件名：{file_ctx.filename}\n"
            "请为后续追问生成一份可复用的文件工作记忆摘要。这不是给用户看的短摘要，而是供后续问答检索使用的工作记忆。"
            "必须尽量保留：文件结构、章节标题、关键数据、专有名词、人名/机构/平台、结论与证据对应关系、风险、限制、待办和建议。"
            "如果有表格或指标，请保留指标名、数值、单位、口径和对比关系。输出要结构化、信息密度高，不要写空泛评价。\n\n"
            f"文件内容：\n{content}"
        )
        summary = self._complete(prompt, task="memory_summary", max_tokens=self.final_summary_tokens)
        file_ctx.summary = summary
        return file_ctx

    def _build_user_content(self, user_message: str, files: list[Any]) -> Any:
        if not files:
            return user_message

        has_multimodal = any(getattr(f, "base64_data", "") or getattr(f, "source_url", "") for f in files)

        if has_multimodal:
            parts = []
            text_sections = [user_message.strip() or "请描述并分析我发送的内容。"]
            text_files = []
            for index, file_ctx in enumerate(files, start=1):
                b64 = getattr(file_ctx, "base64_data", "")
                source_url = getattr(file_ctx, "source_url", "")
                mime = getattr(file_ctx, "mime_type", "")
                if b64 and mime.startswith("image/"):
                    parts.append({"type": "image_url", "image_url": {"url": f"data:{mime};base64,{b64}"}})
                    text_sections.append(f"\n[图片 {index}] {file_ctx.filename}")
                elif b64 and mime.startswith("audio/"):
                    audio_format = mime.split("/")[-1] if "/" in mime else "wav"
                    if audio_format == "mpeg":
                        audio_format = "mp3"
                    elif audio_format == "x-m4a":
                        audio_format = "m4a"
                    parts.append({"type": "input_audio", "input_audio": {"data": b64, "format": audio_format}})
                    text_sections.append(f"\n[音频 {index}] {file_ctx.filename}")
                elif b64 and mime.startswith("video/"):
                    parts.append({"type": "video_url", "video_url": {"url": f"data:{mime};base64,{b64}"}})
                    text_sections.append(f"\n[视频 {index}] {file_ctx.filename}")
                elif source_url and mime.startswith("video/"):
                    parts.append({"type": "video_url", "video_url": {"url": source_url}})
                    text_sections.append(f"\n[视频 {index}] {file_ctx.filename}")
                else:
                    text_files.append((index, file_ctx))

            for index, file_ctx in text_files:
                text_sections.append(f"\n[文件 {index}] {file_ctx.filename}")
                if getattr(file_ctx, "error", ""):
                    text_sections.append(f"解析提示: {file_ctx.error}")
                content = getattr(file_ctx, "content", "")
                if content:
                    text_sections.append("内容：")
                    text_sections.append(content)

            text_sections.append("\n请基于以上内容回答用户，不要编造没有的信息。")
            parts.insert(0, {"type": "text", "text": "\n".join(text_sections)})
            return parts

        prompt = user_message.strip() or self._default_file_analysis_task()
        sections = [prompt, "\n以下是用户上传文件的解析内容："]
        for index, file_ctx in enumerate(files, start=1):
            sections.append(f"\n[文件 {index}] {file_ctx.filename}")
            if getattr(file_ctx, "mime_type", ""):
                sections.append(f"MIME: {file_ctx.mime_type}")
            if getattr(file_ctx, "error", ""):
                sections.append(f"解析提示: {file_ctx.error}")
            content = getattr(file_ctx, "content", "")
            if content:
                sections.append("内容：")
                sections.append(content)
            else:
                sections.append("内容：未能提取文本内容。")
        sections.append("\n请基于这些文件内容回答用户，不要编造文件中没有的信息。")
        return "\n".join(sections)

    def _merge_system_messages(self, messages: list[dict]) -> list[dict]:
        system_parts = []
        non_system = []
        for msg in messages:
            if msg.get("role") == "system":
                system_parts.append(msg.get("content", ""))
            else:
                non_system.append(msg)
        if not system_parts:
            return messages
        merged = [{"role": "system", "content": "\n\n".join(p for p in system_parts if p)}]
        return merged + non_system

    def _build_history_user_content(self, user_message: str, files: list[Any]) -> str:
        if not files:
            return user_message

        prompt = user_message.strip() or "请按结构化简报分析我发送的文件。"
        file_summaries = []
        for file_ctx in files:
            tokens = getattr(file_ctx, "estimated_tokens", 0)
            token_text = f"，约 {tokens:,} tokens" if tokens else ""
            file_summaries.append(f"{file_ctx.filename}{token_text}")
        return f"{prompt}\n[本轮包含文件：{'; '.join(file_summaries)}。文件正文未写入长期历史。]"

    def _complete(self, prompt: str, task: str, max_tokens: int) -> str:
        response = self._create_chat_completion(
            [
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": prompt},
            ],
            task=task,
            max_tokens=max_tokens,
        )
        return response.choices[0].message.content or ""

    def _create_chat_completion(self, messages: list[dict[str, str]], task: str, max_tokens: Optional[int] = None, model_override: Optional[str] = None):
        profile = self._profile(task)
        kwargs = {
            "model": model_override or profile.get("model", self.model),
            "messages": messages,
            "max_tokens": max_tokens or profile.get("max_tokens", self.max_tokens),
            "temperature": profile.get("temperature", self.temperature),
        }
        self._add_optional(kwargs, "top_p", profile.get("top_p", self.top_p))
        self._add_optional(kwargs, "presence_penalty", profile.get("presence_penalty", self.presence_penalty))
        self._add_optional(kwargs, "frequency_penalty", profile.get("frequency_penalty", self.frequency_penalty))
        self._add_optional(kwargs, "seed", profile.get("seed", self.seed))

        extra_body = self._extra_body(task, profile)
        if extra_body:
            kwargs["extra_body"] = extra_body

        if self.stream:
            kwargs["stream"] = True
        if self.stream and self.include_usage:
            kwargs["stream_options"] = {"include_usage": True}

        started = time.time()
        response = self.client.chat.completions.create(**kwargs)
        self._record_usage(task, response, time.time() - started)
        return response

    def _create_streaming_completion(self, messages: list, task: str, model_override: Optional[str] = None) -> str:
        profile = self._profile(task)
        kwargs = {
            "model": model_override or profile.get("model", self.model),
            "messages": messages,
            "max_tokens": profile.get("max_tokens", self.max_tokens),
            "temperature": profile.get("temperature", self.temperature),
            "stream": True,
            "stream_options": {"include_usage": True},
            "modalities": ["text"],
        }
        self._add_optional(kwargs, "top_p", profile.get("top_p", self.top_p))
        self._add_optional(kwargs, "presence_penalty", profile.get("presence_penalty", self.presence_penalty))
        self._add_optional(kwargs, "frequency_penalty", profile.get("frequency_penalty", self.frequency_penalty))
        self._add_optional(kwargs, "seed", profile.get("seed", self.seed))

        extra_body = self._extra_body(task, profile)
        if extra_body:
            kwargs["extra_body"] = extra_body

        started = time.time()
        response = self.client.chat.completions.create(**kwargs)

        text_parts = []
        usage = None
        for chunk in response:
            if chunk.choices and chunk.choices[0].delta.content:
                text_parts.append(chunk.choices[0].delta.content)
            if hasattr(chunk, "usage") and chunk.usage:
                usage = chunk.usage

        elapsed = time.time() - started
        if usage:
            self.last_usage = {
                "task": task,
                "elapsed_sec": round(elapsed, 3),
                "prompt_tokens": getattr(usage, "prompt_tokens", None),
                "completion_tokens": getattr(usage, "completion_tokens", None),
                "total_tokens": getattr(usage, "total_tokens", None),
            }
            logger.info("LLM usage task=%s total=%s prompt=%s completion=%s elapsed=%.2fs",
                        task,
                        self.last_usage["total_tokens"],
                        self.last_usage["prompt_tokens"],
                        self.last_usage["completion_tokens"],
                        elapsed)

        return "".join(text_parts)

    def _profile(self, task: str) -> dict[str, Any]:
        base = self.task_profiles.get("default", {})
        profile = dict(base)
        profile.update(self.task_profiles.get(task, {}))
        return profile

    def _extra_body(self, task: str, profile: dict[str, Any]) -> dict[str, Any]:
        extra = dict(self.dashscope_extra_body)

        enable_search = profile.get("enable_search", self.enable_search)
        if enable_search == "auto":
            enable_search = task == "chat"
        if enable_search is not None:
            extra["enable_search"] = bool(enable_search)

        enable_thinking = profile.get("enable_thinking")
        if enable_thinking is not None:
            extra["enable_thinking"] = bool(enable_thinking)

        thinking_budget = profile.get("thinking_budget")
        if thinking_budget is not None:
            extra["thinking_budget"] = thinking_budget

        search_options = profile.get("search_options")
        if search_options:
            extra["search_options"] = search_options

        return {key: value for key, value in extra.items() if value is not None}

    def _add_optional(self, kwargs: dict[str, Any], key: str, value: Any) -> None:
        if value is not None:
            kwargs[key] = value

    def _record_usage(self, task: str, response: Any, elapsed: float) -> None:
        usage = getattr(response, "usage", None)
        self.last_usage = {
            "task": task,
            "elapsed_sec": round(elapsed, 3),
            "prompt_tokens": getattr(usage, "prompt_tokens", None),
            "completion_tokens": getattr(usage, "completion_tokens", None),
            "total_tokens": getattr(usage, "total_tokens", None),
        }
        if usage:
            logger.info("LLM usage task=%s total=%s prompt=%s completion=%s elapsed=%.2fs",
                        task,
                        self.last_usage["total_tokens"],
                        self.last_usage["prompt_tokens"],
                        self.last_usage["completion_tokens"],
                        elapsed)

    def _build_chunk_prompt(self, user_message: str, file_ctx: Any, chunk: str, index: int, total: int) -> str:
        task = user_message.strip() or self._default_file_analysis_task()
        return (
            f"用户任务：{task}\n"
            f"文件名：{file_ctx.filename}\n"
            f"这是第 {index}/{total} 个分块。请只基于本分块输出高保真摘要，优先保留：章节结构、关键数据、事实依据、结论、风险、异常、限制、行动建议、专有名词、人名/机构/平台名。"
            f"不要把具体数字压缩成泛泛表述；不要省略与用户任务相关的细节。如果本分块与用户任务无关，也要简单说明。\n\n"
            f"分块内容：\n{chunk}"
        )

    def _build_final_summary_prompt(self, user_message: str, file_ctx: Any, chunk_summaries: list[str]) -> str:
        task = user_message.strip() or self._default_file_analysis_task()
        joined = "\n\n".join(f"[分块摘要 {index}]\n{summary}" for index, summary in enumerate(chunk_summaries, start=1))
        return (
            f"用户任务：{task}\n"
            f"文件名：{file_ctx.filename}\n"
            "下面是同一个大文件的分块摘要。请整合为最终回答：去重、合并交叉信息，明确核心结论、关键数据、分模块要点、风险异常、限制条件和行动建议。"
            "要尽量保留重要数字和证据链，不要只给抽象观点，不要编造分块摘要中没有的信息。\n\n"
            f"{joined}"
        )

    def _default_file_analysis_task(self) -> str:
        return (
            "请基于文件内容输出一份结构化分析简报。若文件信息足够，请按以下结构回答：\n"
            "1. 文件主题与目的\n"
            "2. 核心结论\n"
            "3. 关键数据/事实\n"
            "4. 分章节或分模块要点\n"
            "5. 风险、异常、限制或值得追问的点\n"
            "6. 可执行建议\n"
            "请保留重要数字、名称、时间、平台、对比关系和证据，不要为了简洁而丢掉关键信息。"
        )

    def _chunk_text(self, text: str, max_tokens: int) -> list[str]:
        max_chars = max(1000, max_tokens)
        paragraphs = text.splitlines()
        chunks = []
        current = []
        current_len = 0
        for paragraph in paragraphs:
            paragraph_len = max(1, self._estimate_text_tokens(paragraph))
            if current and current_len + paragraph_len > max_tokens:
                chunks.append("\n".join(current).strip())
                current = []
                current_len = 0
            if paragraph_len > max_tokens:
                for start in range(0, len(paragraph), max_chars):
                    piece = paragraph[start:start + max_chars]
                    if piece:
                        chunks.append(piece)
                continue
            current.append(paragraph)
            current_len += paragraph_len
        if current:
            chunks.append("\n".join(current).strip())
        return [chunk for chunk in chunks if chunk]

    def _estimate_text_tokens(self, text: str) -> int:
        if not text:
            return 0
        cjk = 0
        non_cjk = 0
        for char in text:
            code = ord(char)
            if (
                0x4E00 <= code <= 0x9FFF
                or 0x3400 <= code <= 0x4DBF
                or 0x3040 <= code <= 0x30FF
                or 0xAC00 <= code <= 0xD7AF
            ):
                cjk += 1
            elif not char.isspace():
                non_cjk += 1
        return cjk + math.ceil(non_cjk / 4) if non_cjk else cjk
