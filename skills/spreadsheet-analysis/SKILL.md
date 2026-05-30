---
name: spreadsheet-analysis
description: Analyze Excel and CSV files for a data analyst, preserving metrics, data quality issues, trends, segments, anomalies, and actionable recommendations.
file_types: [.xlsx, .xlsm, .csv]
intents: [数据分析, 表格分析, excel, csv, 指标, 趋势, 异常, 汇总, 对比, 透视, 渠道, 转化, 留存, 增长]
priority: 90
enabled: true
---

# Spreadsheet Analysis

Use this skill when the user uploads Excel or CSV data, or asks for metric analysis, trend analysis, data quality checks, channel comparison, conversion analysis, ranking, segmentation, or operational recommendations.

Work like a careful data analyst:

1. Identify the likely grain of the data: one row represents what entity or event.
2. Identify important dimensions, metrics, dates, categories, and possible business meanings.
3. Check data quality before conclusions:
   - missing values
   - duplicated rows or keys
   - suspicious zeros
   - outliers
   - inconsistent units or definitions
4. Summarize key metrics with exact values when available.
5. Compare by meaningful segments, such as channel, platform, city, product, campaign, time, owner, or status.
6. Look for trends, concentration, top/bottom performers, funnel drop-offs, and anomalies.
7. State caveats. Do not invent metrics that are not present.
8. End with actionable next steps.

If the extracted file content is a preview rather than the full workbook, explicitly say the analysis is based on the visible extracted rows/sheets.

Default output structure:

- 数据口径
- 核心结论
- 关键指标
- 分组/趋势/异常洞察
- 数据质量问题
- 建议动作
- 需要补充的数据
