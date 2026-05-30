# WePilot

**[English](README_EN.md)** | 中文

基于微信 iLink 平台的智能聊天机器人，支持多模态理解（图片/音频/视频）、多格式文档解析、大文件分块摘要、对话记忆持久化和可扩展技能系统。

## 功能特性

- **微信消息收发**：通过 iLink Bot API 长轮询接收消息，支持 QR 码扫码登录
- **多模态理解**：支持图片识别、音频识别、视频识别（基于 DashScope 多模态模型）
- **消息引用处理**：支持引用历史消息（图片/视频/音频/文本），自动匹配被引用内容
- **历史文件引用**：通过关键词（"这个"、"那个"、"分析"等）自动关联最近上传的文件
- **多格式文档解析**：PDF、Word、Excel、PPT、CSV、TXT、JSON、代码文件
- **大文件分块摘要**：超大文档自动分块 → 逐块摘要 → 合并分析，支持最多 24 块
- **对话记忆持久化**：基于 JSON 文件的轻量级记忆系统，重启不丢失对话上下文
- **技能系统**：声明式 SKILL.md 定义，自动匹配用户意图，零代码扩展
- **消息去重**：基于消息指纹的 5 分钟 TTL 去重，防止平台重复投递
- **微信加密附件解密**：自动检测并解密 AES 加密的微信附件（支持 ECB/CBC 模式）
- **联网搜索**：支持 DashScope enable_search 实时信息检索
- **视频 URL 提取**：自动识别文本中的视频链接并使用对应模型分析
- **友好提示**：缺少模型配置时，智能提示当前可用功能和配置方法
- **长回复分段**：超长回复自动分段发送，或生成摘要供用户选择查看完整版

## 架构

```
用户消息 → iLink API → MessageParser → DocumentAnalyzer → LLMEngine → 回复
                              ↓                              ↑
                        AttachmentStore              MemoryStore + SkillRuntime
```

| 模块 | 职责 |
|------|------|
| `bot.py` | 主控制器，事件循环，消息处理管道 |
| `ilink_client.py` | 微信 iLink API 通信（登录、收发消息、会话管理） |
| `llm_engine.py` | LLM 调用封装（OpenAI SDK 兼容，多模型自动切换，流式输出） |
| `message_parser.py` | 消息解析（文本提取、附件提取、引用消息解析） |
| `document_analyzer.py` | 文档解析（多格式文本提取、多模态编码、token 估算） |
| `file_service.py` | 文件下载与解密（流式下载、AES 解密、过期清理） |
| `memory_store.py` | 对话记忆（对话摘要、活跃文件、LLM 历史持久化） |
| `skill_runtime.py` | 技能系统（发现、匹配、上下文注入） |
| `replies.py` | 集中管理所有用户可见的回复文本 |

## 快速开始

### 环境要求

- Python 3.9+
- macOS / Linux

### 安装依赖

```bash
pip install -r requirements.txt
```

### 配置

1. 复制配置模板：

```bash
cp config.example.json config.json
```

2. 创建环境变量文件：

```bash
cp .env.example .env
```

3. 编辑 `.env`，填入你的 LLM API Key：

```env
LLM_API_KEY=sk-your-api-key-here
LLM_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
LLM_MODEL=deepseek-v4-pro
```

### 启动

```bash
python3 bot.py
```

首次启动需要用微信扫描二维码登录。登录成功后会话信息保存到 `session.json`，后续启动无需重复扫码。

### 后台运行

```bash
./botctl.sh start     # 后台启动
./botctl.sh stop      # 停止
./botctl.sh restart   # 重启
./botctl.sh status    # 查看状态
./botctl.sh log       # 实时查看日志
```

## 配置说明

### 环境变量（优先级高于 config.json）

| 变量 | 说明 | 必填 |
|------|------|------|
| `LLM_API_KEY` | LLM API 密钥 | 是 |
| `LLM_BASE_URL` | LLM API 地址 | 否 |
| `LLM_MODEL` | 模型名称 | 否 |
| `ILINK_BOT_TOKEN` | iLink Bot Token（通常由扫码登录获取） | 否 |
| `ILINK_BOT_ID` | iLink Bot ID | 否 |
| `ILINK_USER_ID` | iLink User ID | 否 |
| `ILINK_API_BASE_URL` | iLink API 地址 | 否 |

### config.json 主要配置

```jsonc
{
  "llm": {
    "bot_name": "AI助手",        // 机器人名称
    "temperature": 0.7,          // 生成温度
    "max_tokens": 512,           // 最大输出 token
    "max_history": 10,           // 保留最近 N 轮对话
    "reply_style": "concise",    // 回复风格：concise / detailed / humorous
    "enable_search": true,       // 启用联网搜索
    "context_window_tokens": 1000000  // 模型上下文窗口大小
  },
  "multimodal": {
    "enabled": true,             // 是否启用多模态功能
    "provider": "dashscope",     // 多模态服务提供商
    "vision_model": "qwen3.6-plus",       // 图片识别模型
    "audio_model": "qwen3.5-omni-plus",   // 音频识别模型
    "video_model": "qwen3.5-omni-plus",   // 本地视频识别模型（需支持流式输出）
    "video_url_model": "qwen3.6-plus",    // 视频 URL 识别模型
    "max_image_mb": 20,          // 图片最大大小 (MB)
    "max_audio_mb": 100,         // 音频最大大小 (MB)
    "max_video_mb": 300          // 视频最大大小 (MB)
  },
  "files": {
    "max_upload_mb": 200,        // 最大上传文件大小 (MB)
    "max_file_tokens": 850000,   // 单文件最大 token
    "large_file_strategy": "chunk_summary",  // 大文件策略
    "max_chunks": 24,            // 最大分块数
    "upload_retention_days": 30  // 上传文件保留天数
  },
  "memory": {
    "max_recent_turns": 8,       // 保留最近 N 轮对话
    "max_active_files": 3,       // 保留最近 N 个活跃文件
    "max_summary_chars": 6000    // 对话摘要最大字符数
  },
  "reply": {
    "max_chat_chars": 800,       // 单条消息最大字符数
    "auto_split_threshold": 2000, // 自动分段阈值
    "file_output_threshold": 3000, // 文件输出阈值
    "split_delay_seconds": 0.5   // 分段发送延迟
  },
  "skills": {
    "dirs": ["skills", "user_skills"],  // 技能目录
    "max_loaded_skills": 2              // 每轮最多加载技能数
  }
}
```

### 多模态模型配置说明

| 模型类型 | 配置字段 | 推荐模型 | 说明 |
|---------|---------|---------|------|
| 图片识别 | `vision_model` | qwen3.6-plus | 支持 JPG/PNG/GIF/WebP |
| 音频识别 | `audio_model` | qwen3.5-omni-plus | 支持 MP3/WAV/M4A，需流式输出 |
| 本地视频 | `video_model` | qwen3.5-omni-plus | 支持 MP4/MOV/AVI，需流式输出 |
| 视频 URL | `video_url_model` | qwen3.6-plus | 支持文本中的视频链接 |

> **注意**：如果某个模型未配置，机器人会自动提示用户当前可用的功能和配置方法。

### 任务配置 (task_profiles)

不同任务使用不同的 LLM 参数组合：

| 任务 | temperature | max_tokens | 用途 |
|------|-------------|------------|------|
| `chat` | 0.7 | 1000 | 日常对话 |
| `file_analysis` | 0.2 | 8192 | 文件分析 |
| `chunk_summary` | 0.2 | 2048 | 分块摘要 |
| `memory_summary` | 0.1 | 8192 | 记忆摘要 |

## 技能系统

技能通过 `SKILL.md` 文件声明式定义，支持自动匹配用户意图和文件类型。

### 内置技能

| 技能 | 文件类型 | 功能 |
|------|---------|------|
| `docx-enhanced` | .docx | Word 创建/编辑/追踪修订 |
| `pptx-enhanced` | .pptx | PPT 创建/设计/编辑 |
| `xlsx-enhanced` | .xlsx/.csv | Excel 数据处理/公式/财务模型 |
| `pdf-enhanced` | .pdf | PDF 提取/创建/合并/OCR |
| `data-brief` | 多格式 | 业务数据简报生成 |
| `pdf-report-analysis` | .pdf | PDF 报告深度分析 |
| `spreadsheet-analysis` | .xlsx/.csv | 电子表格数据分析 |
| `presentation-analysis` | .pptx | PPT 演示文稿分析 |
| `document-analysis` | .docx/.md/.txt | 文档内容分析 |

### 自定义技能

在 `user_skills/` 目录下创建新技能：

```
user_skills/my-skill/SKILL.md
```

SKILL.md 格式：

```markdown
---
name: my-skill
description: 技能描述
file_types: [.xlsx, .csv]
intents: [数据分析, 报表]
priority: 100
enabled: true
---

# 技能详细指令

在这里定义工作流、输出格式、注意事项等。
```

## 项目结构

```
WePilot/
├── bot.py                  # 主入口，消息处理管道
├── ilink_client.py         # iLink API 客户端（登录、收发消息）
├── llm_engine.py           # LLM 引擎（多模型切换、流式输出）
├── message_parser.py       # 消息解析（文本、附件、引用消息）
├── document_analyzer.py    # 文档解析（多格式、多模态编码）
├── file_service.py         # 文件下载与解密（AES ECB/CBC）
├── memory_store.py         # 对话记忆（摘要、活跃文件、历史）
├── skill_runtime.py        # 技能系统（发现、匹配、注入）
├── replies.py              # 用户可见回复文本集中管理
├── botctl.sh               # 管理脚本（start/stop/restart/status/log）
├── config.json             # 运行时配置（不提交）
├── config.example.json     # 配置模板
├── .env                    # 环境变量（不提交）
├── .env.example            # 环境变量模板
├── session.json            # 登录会话（不提交）
├── requirements.txt        # Python 依赖
├── skills/                 # 内置技能
│   ├── docx-enhanced/      # Word 创建/编辑
│   ├── pptx-enhanced/      # PPT 创建/设计
│   ├── xlsx-enhanced/      # Excel 数据处理
│   ├── pdf-enhanced/       # PDF 提取/创建
│   ├── data-brief/         # 业务数据简报
│   ├── pdf-report-analysis/    # PDF 报告分析
│   ├── spreadsheet-analysis/   # 电子表格分析
│   ├── presentation-analysis/  # PPT 分析
│   └── document-analysis/      # 文档内容分析
├── user_skills/            # 用户自定义技能
│   └── media-data-analyst/ # 媒体数据分析
└── data/
    ├── bot.pid             # 进程锁
    ├── bot.log             # 运行日志
    ├── uploads/            # 上传文件（按用户/日期组织）
    ├── memory/             # 对话记忆（JSON）
    └── debug_messages/     # 调试消息（引用消息等）
```

## 消息处理流程

```
1. 接收消息 → 去重检查
2. 解析消息 → 提取文本、附件、引用内容
3. 下载附件 → 流式下载 + AES 解密
4. 分析文件 → 文档解析 / 多模态编码（base64）
5. 历史引用 → 关键词匹配 / 时间戳匹配
6. 构建上下文 → 对话摘要 + 活跃文件 + 历史记录
7. 选择技能 → 意图匹配 + 文件类型匹配
8. 调用 LLM → 自动选择模型（文本/图片/音频/视频）
9. 处理回复 → 分段发送 / 摘要缓存
10. 记录记忆 → 更新对话历史 + 活跃文件
```

## 多模态支持

### 支持的媒体类型

| 类型 | 格式 | 模型 | 处理方式 |
|------|------|------|---------|
| 图片 | JPG/PNG/GIF/WebP | vision_model | base64 编码 → image_url |
| 音频 | MP3/WAV/M4A | audio_model | base64 编码 → input_audio（流式） |
| 视频（本地） | MP4/MOV/AVI | video_model | base64 编码 → video_url（流式） |
| 视频（URL） | 文本中的链接 | video_url_model | 直接传入 URL |

### 消息引用处理

当用户引用历史消息时，系统会：

1. **完整引用**：iLink 返回完整的 `ref_msg.message_item`（含附件数据）→ 直接解析
2. **空壳引用**：iLink 只返回 `create_time_ms` 时间戳 → 通过时间戳匹配上传目录中的文件（容差 5 秒）

### 历史文件引用

当用户说"分析这个"、"看看那个"等关键词时，系统会：
- 检查最近对话中是否有文件
- 在上传目录中查找对应文件
- 自动加载并分析

> **注意**：如果用户显式引用了消息（有 `ref_msg`），则不会触发历史文件猜测。

## 测试

```bash
# 进程锁测试
python3 test_process_lock.py

# 手动编译检查
python3 -c "import py_compile; [py_compile.compile(f, doraise=True) for f in ['bot.py', 'llm_engine.py', 'memory_store.py', 'ilink_client.py', 'message_parser.py', 'document_analyzer.py', 'file_service.py', 'skill_runtime.py']]"
```

## 安全注意事项

- `config.json`、`session.json`、`.env` 已加入 `.gitignore`，不会被提交
- API Key 通过环境变量管理，不要明文写入配置文件
- 调试消息自动脱敏 token/ticket/authorization 字段
- 文件下载有大小限制（默认 200MB），防止磁盘溢出
- 上传文件自动清理（默认 30 天），防止磁盘占满
- 微信附件使用 AES 加密，密钥从消息中提取，解密后存储本地

### 命令安全拦截

系统内置了危险命令检测机制，会自动拦截以下类型的输入：

**危险操作命令：**
- 删除类：`rm`、`del`、`delete`、`remove`、`删除`、`清除`、`清空`
- 数据库类：`drop`、`truncate`、`alter table`
- 进程类：`kill`、`pkill`、`killall`、`终止`、`杀死`
- 系统类：`format`、`格式化`、`初始化`、`shutdown`、`reboot`、`关机`、`重启`

**注入攻击尝试：**
- Shell 特殊字符：`;`、`|`、`&`、`` ` ``、`$`
- 代码执行函数：`eval`、`exec`、`system`、`os.system`、`subprocess`
- XSS 攻击：`<script>`、`javascript:`、`onerror=`
- SQL 注入：`union select`、`insert into`、`update ... set`

当检测到危险命令时，系统会：
1. 记录警告日志
2. 向用户发送友好提示，说明该操作不被允许
3. 建议用户使用微信客户端的原生功能管理聊天记录

> **注意**：用户只能在自己的聊天记录中执行删除操作，系统不会执行任何危险命令。

## 快速配置

### 最小配置（仅文本对话）

只需配置 `llm` 部分即可使用基本的文本对话和文档解析功能。

### 完整配置（多模态）

配置 `multimodal` 部分可启用图片/音频/视频识别功能。如果某个模型未配置，机器人会自动提示用户当前可用的功能和配置方法。

## 开源协议

本项目基于 [MIT License](LICENSE) 开源。

你可以自由地：
- 使用、复制、修改、合并、出版发行、散布、再授权和贩售本软件的副本
- 在软件中提供上述权利

唯一要求：在软件的所有副本中包含版权声明和许可声明。
