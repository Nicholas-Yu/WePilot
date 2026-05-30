# WeChat iLink Bot

**English** | **[中文](README.md)**

An intelligent chatbot based on the WeChat iLink platform, supporting multimodal understanding (image/audio/video), multi-format document parsing, large file chunked summarization, persistent conversation memory, and an extensible skill system.

## Features

- **WeChat Messaging**: Long-polling message reception via iLink Bot API, QR code login support
- **Multimodal Understanding**: Image recognition, audio recognition, video recognition (based on DashScope multimodal models)
- **Message Quoting**: Support for quoting historical messages (image/video/audio/text) with automatic content matching
- **Historical File Reference**: Automatic association with recently uploaded files via keywords ("this", "that", "analyze", etc.)
- **Multi-format Document Parsing**: PDF, Word, Excel, PPT, CSV, TXT, JSON, code files
- **Large File Chunked Summary**: Automatic chunking → per-chunk summarization → merged analysis, supporting up to 24 chunks
- **Persistent Conversation Memory**: Lightweight JSON-based memory system, context preserved across restarts
- **Skill System**: Declarative SKILL.md definitions, automatic intent matching, zero-code extension
- **Message Deduplication**: 5-minute TTL deduplication based on message fingerprints
- **WeChat Encrypted Attachment Decryption**: Automatic detection and decryption of AES-encrypted WeChat attachments (ECB/CBC modes)
- **Web Search**: Real-time information retrieval via DashScope enable_search
- **Video URL Extraction**: Automatic detection and analysis of video links in text
- **Friendly Prompts**: Intelligent prompts showing available features and configuration methods when models are not configured
- **Long Reply Segmentation**: Automatic segmentation of long replies, or summary generation for user selection

## Architecture

```
User Message → iLink API → MessageParser → DocumentAnalyzer → LLMEngine → Reply
                                    ↓                              ↑
                              AttachmentStore              MemoryStore + SkillRuntime
```

| Module | Responsibility |
|--------|----------------|
| `bot.py` | Main controller, event loop, message processing pipeline |
| `ilink_client.py` | WeChat iLink API communication (login, send/receive messages, session management) |
| `llm_engine.py` | LLM call wrapper (OpenAI SDK compatible, multi-model switching, streaming output) |
| `message_parser.py` | Message parsing (text extraction, attachment extraction, quoted message parsing) |
| `document_analyzer.py` | Document parsing (multi-format text extraction, multimodal encoding, token estimation) |
| `file_service.py` | File download and decryption (streaming download, AES decryption, expiration cleanup) |
| `memory_store.py` | Conversation memory (dialogue summary, active files, LLM history persistence) |
| `skill_runtime.py` | Skill system (discovery, matching, context injection) |
| `replies.py` | Centralized management of all user-visible reply texts |

## Quick Start

### Requirements

- Python 3.9+
- macOS / Linux

### Install Dependencies

```bash
pip install -r requirements.txt
```

### Configuration

1. Copy the configuration template:

```bash
cp config.example.json config.json
```

2. Create the environment variables file:

```bash
cp .env.example .env
```

3. Edit `.env` and fill in your LLM API Key:

```env
LLM_API_KEY=sk-your-api-key-here
LLM_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
LLM_MODEL=deepseek-v4-pro
```

### Start

```bash
python3 bot.py
```

On first launch, you need to scan the QR code with WeChat to log in. After successful login, session information is saved to `session.json`, and subsequent launches do not require re-scanning.

### Run in Background

```bash
./botctl.sh start     # Start in background
./botctl.sh stop      # Stop
./botctl.sh restart   # Restart
./botctl.sh status    # Check status
./botctl.sh log       # View logs in real-time
```

## Configuration

### Environment Variables (Higher Priority than config.json)

| Variable | Description | Required |
|----------|-------------|----------|
| `LLM_API_KEY` | LLM API key | Yes |
| `LLM_BASE_URL` | LLM API endpoint | No |
| `LLM_MODEL` | Model name | No |
| `ILINK_BOT_TOKEN` | iLink Bot Token (usually obtained via QR login) | No |
| `ILINK_BOT_ID` | iLink Bot ID | No |
| `ILINK_USER_ID` | iLink User ID | No |
| `ILINK_API_BASE_URL` | iLink API endpoint | No |

### config.json Main Configuration

```jsonc
{
  "llm": {
    "bot_name": "AI Assistant",     // Bot name
    "temperature": 0.7,             // Generation temperature
    "max_tokens": 512,              // Max output tokens
    "max_history": 10,              // Keep last N conversation turns
    "reply_style": "concise",       // Reply style: concise / detailed / humorous
    "enable_search": true,          // Enable web search
    "context_window_tokens": 1000000  // Model context window size
  },
  "multimodal": {
    "enabled": true,                // Enable multimodal features
    "provider": "dashscope",        // Multimodal service provider
    "vision_model": "qwen3.6-plus",       // Image recognition model
    "audio_model": "qwen3.5-omni-plus",   // Audio recognition model
    "video_model": "qwen3.5-omni-plus",   // Local video recognition model (requires streaming)
    "video_url_model": "qwen3.6-plus",    // Video URL recognition model
    "max_image_mb": 20,             // Max image size (MB)
    "max_audio_mb": 100,            // Max audio size (MB)
    "max_video_mb": 300             // Max video size (MB)
  },
  "files": {
    "max_upload_mb": 200,           // Max upload file size (MB)
    "max_file_tokens": 850000,      // Max tokens per file
    "large_file_strategy": "chunk_summary",  // Large file strategy
    "max_chunks": 24,               // Max number of chunks
    "upload_retention_days": 30     // Upload file retention days
  },
  "memory": {
    "max_recent_turns": 8,          // Keep last N conversation turns
    "max_active_files": 3,          // Keep last N active files
    "max_summary_chars": 6000       // Max dialogue summary characters
  },
  "reply": {
    "max_chat_chars": 800,          // Max characters per message
    "auto_split_threshold": 2000,   // Auto-split threshold
    "file_output_threshold": 3000,  // File output threshold
    "split_delay_seconds": 0.5      // Split send delay
  },
  "skills": {
    "dirs": ["skills", "user_skills"],  // Skill directories
    "max_loaded_skills": 2              // Max skills loaded per turn
  }
}
```

### Multimodal Model Configuration

| Model Type | Config Field | Recommended Model | Description |
|------------|--------------|-------------------|-------------|
| Image Recognition | `vision_model` | qwen3.6-plus | Supports JPG/PNG/GIF/WebP |
| Audio Recognition | `audio_model` | qwen3.5-omni-plus | Supports MP3/WAV/M4A, requires streaming |
| Local Video | `video_model` | qwen3.5-omni-plus | Supports MP4/MOV/AVI, requires streaming |
| Video URL | `video_url_model` | qwen3.6-plus | Supports video links in text |

> **Note**: If a model is not configured, the bot will automatically prompt the user with available features and configuration methods.

### Task Profiles

Different tasks use different LLM parameter combinations:

| Task | temperature | max_tokens | Purpose |
|------|-------------|------------|---------|
| `chat` | 0.7 | 1000 | Daily conversation |
| `file_analysis` | 0.2 | 8192 | File analysis |
| `chunk_summary` | 0.2 | 2048 | Chunk summarization |
| `memory_summary` | 0.1 | 8192 | Memory summarization |

## Skill System

Skills are declaratively defined via `SKILL.md` files, supporting automatic matching of user intent and file types.

### Built-in Skills

| Skill | File Types | Function |
|-------|------------|----------|
| `docx-enhanced` | .docx | Word creation/editing/track changes |
| `pptx-enhanced` | .pptx | PPT creation/design/editing |
| `xlsx-enhanced` | .xlsx/.csv | Excel data processing/formulas/financial models |
| `pdf-enhanced` | .pdf | PDF extraction/creation/merging/OCR |
| `data-brief` | Multi-format | Business data brief generation |
| `pdf-report-analysis` | .pdf | PDF report deep analysis |
| `spreadsheet-analysis` | .xlsx/.csv | Spreadsheet data analysis |
| `presentation-analysis` | .pptx | PPT presentation analysis |
| `document-analysis` | .docx/.md/.txt | Document content analysis |

### Custom Skills

Create new skills in the `user_skills/` directory:

```
user_skills/my-skill/SKILL.md
```

SKILL.md format:

```markdown
---
name: my-skill
description: Skill description
file_types: [.xlsx, .csv]
intents: [data analysis, report]
priority: 100
enabled: true
---

# Skill Detailed Instructions

Define workflow, output format, notes, etc. here.
```

## Project Structure

```
wechat-ilink-bot/
├── bot.py                  # Main entry, message processing pipeline
├── ilink_client.py         # iLink API client (login, send/receive messages)
├── llm_engine.py           # LLM engine (multi-model switching, streaming)
├── message_parser.py       # Message parsing (text, attachments, quoted messages)
├── document_analyzer.py    # Document parsing (multi-format, multimodal encoding)
├── file_service.py         # File download and decryption (AES ECB/CBC)
├── memory_store.py         # Conversation memory (summary, active files, history)
├── skill_runtime.py        # Skill system (discovery, matching, injection)
├── replies.py              # Centralized user-visible reply text management
├── botctl.sh               # Management script (start/stop/restart/status/log)
├── config.json             # Runtime configuration (not committed)
├── config.example.json     # Configuration template
├── .env                    # Environment variables (not committed)
├── .env.example            # Environment variables template
├── session.json            # Login session (not committed)
├── requirements.txt        # Python dependencies
├── skills/                 # Built-in skills
│   ├── docx-enhanced/      # Word creation/editing
│   ├── pptx-enhanced/      # PPT creation/design
│   ├── xlsx-enhanced/      # Excel data processing
│   ├── pdf-enhanced/       # PDF extraction/creation
│   ├── data-brief/         # Business data brief
│   ├── pdf-report-analysis/    # PDF report analysis
│   ├── spreadsheet-analysis/   # Spreadsheet analysis
│   ├── presentation-analysis/  # PPT analysis
│   └── document-analysis/      # Document content analysis
├── user_skills/            # User custom skills
│   └── media-data-analyst/ # Media data analysis
└── data/
    ├── bot.pid             # Process lock
    ├── bot.log             # Runtime logs
    ├── uploads/            # Uploaded files (organized by user/date)
    ├── memory/             # Conversation memory (JSON)
    └── debug_messages/     # Debug messages (quoted messages, etc.)
```

## Message Processing Flow

```
1. Receive message → Deduplication check
2. Parse message → Extract text, attachments, quoted content
3. Download attachments → Streaming download + AES decryption
4. Analyze files → Document parsing / Multimodal encoding (base64)
5. Historical reference → Keyword matching / Timestamp matching
6. Build context → Dialogue summary + Active files + History records
7. Select skills → Intent matching + File type matching
8. Call LLM → Auto-select model (text/image/audio/video)
9. Process reply → Segmented sending / Summary caching
10. Record memory → Update dialogue history + Active files
```

## Multimodal Support

### Supported Media Types

| Type | Format | Model | Processing Method |
|------|--------|-------|-------------------|
| Image | JPG/PNG/GIF/WebP | vision_model | base64 encoding → image_url |
| Audio | MP3/WAV/M4A | audio_model | base64 encoding → input_audio (streaming) |
| Video (Local) | MP4/MOV/AVI | video_model | base64 encoding → video_url (streaming) |
| Video (URL) | Links in text | video_url_model | Direct URL input |

### Message Quoting

When users quote historical messages, the system will:

1. **Complete Quote**: iLink returns complete `ref_msg.message_item` (with attachment data) → Direct parsing
2. **Shell Quote**: iLink only returns `create_time_ms` timestamp → Match files in upload directory by timestamp (5-second tolerance)

### Historical File Reference

When users say "analyze this", "look at that", etc., the system will:
- Check if there are files in recent conversations
- Search for corresponding files in the upload directory
- Automatically load and analyze

> **Note**: If users explicitly quote a message (with `ref_msg`), historical file guessing will not be triggered.

## Testing

```bash
# Process lock test
python3 test_process_lock.py

# Manual compilation check
python3 -c "import py_compile; [py_compile.compile(f, doraise=True) for f in ['bot.py', 'llm_engine.py', 'memory_store.py', 'ilink_client.py', 'message_parser.py', 'document_analyzer.py', 'file_service.py', 'skill_runtime.py']]"
```

## Security Considerations

- `config.json`, `session.json`, `.env` are added to `.gitignore` and will not be committed
- API Keys are managed via environment variables, do not write them in plain text to configuration files
- Debug messages automatically redact token/ticket/authorization fields
- File downloads have size limits (default 200MB) to prevent disk overflow
- Uploaded files are automatically cleaned (default 30 days) to prevent disk filling
- WeChat attachments use AES encryption, keys are extracted from messages, decrypted and stored locally

### Command Security Interception

The system has built-in dangerous command detection that automatically intercepts the following types of input:

**Dangerous Operation Commands:**
- Delete: `rm`, `del`, `delete`, `remove`
- Database: `drop`, `truncate`, `alter table`
- Process: `kill`, `pkill`, `killall`
- System: `format`, `shutdown`, `reboot`, `restart`

**Injection Attack Attempts:**
- Shell special characters: `;`, `|`, `&`, `` ` ``, `$`
- Code execution functions: `eval`, `exec`, `system`, `os.system`, `subprocess`
- XSS attacks: `<script>`, `javascript:`, `onerror=`
- SQL injection: `union select`, `insert into`, `update ... set`

When dangerous commands are detected, the system will:
1. Log a warning
2. Send a friendly prompt to the user explaining the operation is not allowed
3. Suggest users use WeChat client's native features to manage chat history

> **Note**: Users can only perform delete operations in their own chat history, the system will not execute any dangerous commands.

## Open Source

This project supports open source use, users can configure different LLM models as needed:

### Minimal Configuration (Text Only)

Only configure the `llm` section to use basic text conversation and document parsing features.

### Full Configuration (Multimodal)

Configure the `multimodal` section to enable image/audio/video recognition features. If a model is not configured, the bot will automatically prompt the user with available features and configuration methods.

## Changelog

### v2.0 (2026-05-30)

- **Added**: Multimodal understanding (image/audio/video recognition)
- **Added**: Message quoting (support for quoting historical images/videos/audio/text)
- **Added**: Historical file reference (keyword matching + timestamp matching)
- **Added**: Automatic video URL extraction and analysis
- **Added**: Friendly prompts (show available features when models are not configured)
- **Added**: Long reply segmentation and summary caching
- **Added**: `replies.py` centralized management of all user-visible replies
- **Added**: Dangerous command security interception (delete/injection/system command detection)
- **Optimized**: LLM engine supports multi-model auto-switching
- **Optimized**: Streaming output support (qwen3.5-omni-plus)
- **Optimized**: System message auto-merging (compatible with multimodal models)
- **Optimized**: AES decryption supports ECB/CBC dual modes
- **Optimized**: Automatic file expiration cleanup

### v1.0 (2026-05-07)

- Initial release: Text conversation, document parsing, conversation memory, skill system
