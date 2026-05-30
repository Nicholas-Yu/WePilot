---
name: document-analysis
description: Analyze Word, Markdown, and general text documents with high fidelity for summaries, decisions, risks, action items, and reusable working memory.
file_types: [.docx, .md, .txt]
intents: [文档, 总结, 提炼, 会议纪要, 需求, 行动项, 风险, 改写, 审阅, 报告]
priority: 70
enabled: true
---

# Document Analysis

Use this skill for Word, Markdown, and text documents.

Preserve structure and facts. Do not compress the document into a vague summary. Keep names, dates, organizations, product names, section titles, claims, evidence, metrics, risks, decisions, open questions, and action items.

Default output structure:

- 文档主题与目的
- 结构/章节梳理
- 核心结论
- 关键事实与证据
- 风险、分歧、限制或待确认事项
- 行动项和责任建议
- 适合后续追问的索引

If the user asks for rewriting, produce the rewrite first, then briefly explain major changes.
