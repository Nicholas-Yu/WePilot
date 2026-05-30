DOWNLOAD_FAILED = "文件我收到了，但下载时出了点问题。你可以稍后再发一次试试，或者换个格式发给我～"

UNPROCESSABLE_HEADER = "文件我收到了，但暂时没法完整解析："

UNPROCESSABLE_FOOTER = "你可以试试重新发一次，或者换成 PDF、Word、Excel、TXT、图片（JPG/PNG）、音频（MP3/WAV）、视频（MP4/MOV）等格式～"

CHUNKING_NOTICE = "这个文件比较大，我需要一点时间来仔细看完。稍等我一下哈～"

CHUNKING_FILE_LINE = "- {filename}：约 {tokens:,} 字"

LONG_REPLY_SUMMARY_PROMPT = '以上是核心要点。内容比较长，需要我发完整版吗？回复"要"就行～'

REPORT_EXPIRED = "哎呀，之前的内容已经过期了，你重新问我一次吧～"

REPORT_SENDING_NOTICE = "好的，内容比较长，我分 {count} 条发给你哈："

MULTIMODAL_DISABLED = "目前多模态功能还没有开启，暂时只能处理文字和文档哦～\n\n如果需要识别图片/音视频，可以在 config.json 的 multimodal 字段中配置：\n  - 开启功能：设置 enabled 为 true\n  - 图片识别：配置 vision_model（例如 qwen3.6-plus）\n  - 音频识别：配置 audio_model（例如 qwen3.5-omni-plus）\n  - 视频识别：配置 video_model（例如 qwen3.5-omni-plus）"

FILE_TOO_LARGE = "这个文件有点大（{size:.1f}MB），目前最多支持 {limit}MB，你可以压缩一下再发给我～"

VISION_MODEL_NOT_SET = "图片识别功能还没配置哦～\n\n目前支持的功能：\n  ✅ 文字对话\n  ✅ 文档解析（PDF/Word/Excel/TXT）\n  ❌ 图片识别（未配置）\n  ❌ 音频识别（需配置）\n  ❌ 视频识别（需配置）\n\n如果需要识别图片，可以在 config.json 的 multimodal 字段中配置 vision_model（例如 qwen3.6-plus），或者你可以先用文字描述给我～"

AUDIO_MODEL_NOT_SET = "音频识别功能还没配置哦～\n\n目前支持的功能：\n  ✅ 文字对话\n  ✅ 文档解析（PDF/Word/Excel/TXT）\n  ⚠️ 图片识别（取决于配置）\n  ❌ 音频识别（未配置）\n  ❌ 视频识别（需配置）\n\n如果需要识别音频，可以在 config.json 的 multimodal 字段中配置 audio_model（例如 qwen3.5-omni-plus），或者你可以把想说的打字发给我～"

VIDEO_MODEL_NOT_SET = "视频识别功能还没配置哦～\n\n目前支持的功能：\n  ✅ 文字对话\n  ✅ 文档解析（PDF/Word/Excel/TXT）\n  ⚠️ 图片识别（取决于配置）\n  ⚠️ 音频识别（取决于配置）\n  ❌ 视频识别（未配置）\n\n如果需要识别视频，可以在 config.json 的 multimodal 字段中配置 video_model（例如 qwen3.5-omni-plus），或者你可以发视频链接、截几张关键画面的图发给我～"

IMAGE_ENCODE_FAILED = "图片处理时出了点问题，你可以试试重新发一次，或者换个图片格式（JPG/PNG）～"

AUDIO_ENCODE_FAILED = "音频处理时出了点问题，你可以试试重新发一次，或者换个音频格式（MP3/WAV/M4A）～"

VIDEO_ENCODE_FAILED = "视频处理时出了点问题，你可以试试重新发一次，或者换个视频格式（MP4/MOV/AVI）～"

VIDEO_NOT_SUPPORTED = "这种视频格式我暂时还不认识，你可以换成常见的视频格式（MP4/MOV/AVI）发给我～"

AUDIO_NOT_SUPPORTED = "这种音频格式我暂时还不认识，你可以换成常见的音频格式（MP3/WAV/M4A）发给我～"

UNSUPPORTED_MULTIMODAL = "这种文件格式我暂时还不认识，你可以换成常见的图片格式（JPG/PNG）或者文档格式发给我～"

UNSUPPORTED_FORMAT = "这个文件格式我暂时还不认识，你可以试试发 PDF、Word、Excel、TXT 给我～"

PARSE_FAILED = "文件解析时出了点问题，你可以试试重新发一次，或者换个格式试试～"

DEPENDENCY_MISSING_PDF = "PDF 解析功能暂时不可用，请稍后再试～"

DEPENDENCY_MISSING_DOCX = "Word 文档解析功能暂时不可用，请稍后再试～"

DEPENDENCY_MISSING_XLSX = "Excel 解析功能暂时不可用，请稍后再试～"

FILE_TOO_LONG = "这个文件内容太长了，我一次看不完。你可以试试分段发给我，或者告诉我你最关心哪部分～"

VIDEO_PROCESSING = "视频正在处理中，请稍等片刻～"

AUDIO_PROCESSING = "音频正在处理中，请稍等片刻～"

LLM_ERROR = "我脑子突然卡了一下，你再说一次试试？"

UPLOAD_TOO_LARGE = "这个文件有点大（{size:.1f}MB），目前最多支持 {limit:.0f}MB，你可以压缩一下再发给我～"

DANGEROUS_COMMAND_BLOCKED = "⚠️ 检测到潜在的危险操作，已拦截。\n\n为了安全起见，系统不允许执行删除、清除等危险命令。如果你需要管理自己的聊天记录，请使用微信客户端的删除功能。\n\n我只能帮你分析文件、回答问题，不能执行系统命令哦～"

INJECTION_ATTEMPT_BLOCKED = "⚠️ 检测到异常输入，已拦截。\n\n请不要尝试注入代码或执行系统命令，这可能会影响系统安全。\n\n有什么我可以帮你的吗？"

MULTIMODAL_RECEIVED_IMAGE = "图片收到啦～你想让我帮你看看什么？比如描述内容、提取文字、分析图表等，告诉我你的需求就好～"

MULTIMODAL_RECEIVED_AUDIO = "音频收到啦～你想让我帮你做什么？比如转文字、总结内容、翻译等，告诉我你的需求就好～"

MULTIMODAL_RECEIVED_VIDEO = "视频收到啦～你想让我帮你做什么？比如总结内容、提取关键画面等，告诉我你的需求就好～"

MULTIMODAL_RECEIVED_MULTI = "文件都收到啦～你想让我帮你做什么分析？告诉我具体需求就好～"

MULTIMODAL_AUTO_ANALYZE = "看你还没说具体要求，我先帮你看看这些内容哈～如果有其他想了解的，随时告诉我～"
