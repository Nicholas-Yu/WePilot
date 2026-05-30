---
name: pdf-report-analysis
description: Analyze PDF reports, preserving report structure, key metrics, tables, evidence, assumptions, and caveats.
file_types: [.pdf]
intents: [pdf, 研报, 报告, 财报, 简报, 指标, 结论, 风险, 摘要]
priority: 75
enabled: true
---

# PDF Report Analysis

Use this skill for PDF reports.

Treat extracted PDF text as potentially imperfect. If pages, tables, headers, or footnotes appear garbled, say so. Preserve page markers when useful.

Analysis checklist:

1. Identify report topic, period, publisher, and scope.
2. Extract major conclusions and supporting evidence.
3. Preserve important metrics, numbers, definitions, and caveats.
4. Separate facts from interpretation.
5. Highlight tables or chart descriptions if extracted.
6. Note missing context or extraction limitations.

Default output structure:

- 报告范围
- 一句话结论
- 核心发现
- 关键数据/表格
- 风险与限制
- 对数据分析师有用的后续问题
