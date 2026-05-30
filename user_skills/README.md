Put your own Anthropic-compatible skills here.

Each skill should live in its own folder and include a `SKILL.md` file:

```text
user_skills/my-channel-analysis/SKILL.md
```

Minimum `SKILL.md` format:

```markdown
---
name: my-channel-analysis
description: Analyze channel performance using my internal methodology.
file_types: [.xlsx, .csv, .docx]
intents: [渠道分析, 传播复盘, 新媒体]
priority: 100
enabled: true
---

# My Channel Analysis

Describe your workflow, definitions, preferred output structure, and caveats here.
```

Higher `priority` wins over built-in skills when multiple skills match.
