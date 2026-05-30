---
name: pdf-enhanced
description: 专业的PDF文档处理技能，支持文本提取、表格提取、PDF创建、合并分割、水印添加、密码保护和OCR识别。当用户提到PDF、合并PDF、分割PDF、PDF转文本、提取表格、扫描件OCR、添加水印等操作时使用此技能。
file_types: [.pdf]
intents: [pdf, 合并pdf, 分割pdf, pdf转文本, 提取表格, ocr, 扫描件, 水印, pdf密码, pdf加密]
priority: 85
enabled: true
license: Based on Anthropic official PDF skill
---

# PDF处理技能（增强版）

本技能整合Anthropic官方PDF技能最佳实践，专为中文文档场景优化。

## 核心库推荐

| 任务 | 推荐库 | 安装命令 |
|------|--------|---------|
| 基础读写/合并/分割 | `pypdf` | `pip install pypdf` |
| 文本/表格提取 | `pdfplumber` | `pip install pdfplumber` |
| PDF创建 | `reportlab` | `pip install reportlab` |
| OCR识别 | `pytesseract` + `pdf2image` | `pip install pytesseract pdf2image` |

## 基础操作

### 读取PDF并提取文本

```python
from pypdf import PdfReader

reader = PdfReader("document.pdf")
print(f"页数: {len(reader.pages)}")

# 提取文本
text = ""
for page in reader.pages:
    text += page.extract_text() or ""
```

### 提取表格（推荐）

```python
import pdfplumber
import pandas as pd

with pdfplumber.open("document.pdf") as pdf:
    all_tables = []
    for page in pdf.pages:
        tables = page.extract_tables()
        for table in tables:
            if table:
                df = pd.DataFrame(table[1:], columns=table[0])
                all_tables.append(df)
    
    # 合并所有表格并导出
    if all_tables:
        combined_df = pd.concat(all_tables, ignore_index=True)
        combined_df.to_excel("extracted_tables.xlsx", index=False)
```

## 文本提取注意事项

### 中文PDF提取

中文PDF提取可能存在以下问题：
- **扫描件**：需要OCR处理
- **图片嵌入文本**：需要OCR
- **矢量文字乱码**：可能是字体编码问题
- **表格错位**：尝试使用`pdfplumber`的`table_settings`参数调整

```python
# 表格提取参数调整
with pdfplumber.open("document.pdf") as pdf:
    for page in pdf.pages:
        # 调整表格检测参数
        tables = page.extract_tables(table_settings={
            "vertical_strategy": "text",
            "horizontal_strategy": "text",
            "intersection_tolerance": 5
        })
```

### OCR处理扫描件

```python
from pytesseract import image_to_string
from pdf2image import convert_from_path

# 将PDF转换为图片
images = convert_from_path('scanned.pdf')

# OCR识别
text = ""
for i, image in enumerate(images):
    page_text = image_to_string(image, lang='chi_sim+eng')
    text += f"[第 {i+1} 页]\n{page_text}\n\n"

print(text)
```

**注意**：需要安装Tesseract OCR引擎：
- macOS: `brew install tesseract tesseract-lang`
- Ubuntu: `sudo apt-get install tesseract-ocr tesseract-ocr-chi-sim`

## PDF合并与分割

### 合并多个PDF

```python
from pypdf import PdfWriter, PdfReader

writer = PdfWriter()
for pdf_file in ["doc1.pdf", "doc2.pdf", "doc3.pdf"]:
    reader = PdfReader(pdf_file)
    for page in reader.pages:
        writer.add_page(page)

with open("merged.pdf", "wb") as output:
    writer.write(output)
```

### 分割PDF

```python
reader = PdfReader("input.pdf")
for i, page in enumerate(reader.pages):
    writer = PdfWriter()
    writer.add_page(page)
    with open(f"page_{i+1}.pdf", "wb") as output:
        writer.write(output)
```

## 创建PDF

### 使用reportlab创建中文PDF

**重要**：reportlab内置字体不支持中文，需要配置中文字体！

```python
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet

# 注册中文字体
pdfmetrics.registerFont(TTFont('SimSun', '/System/Library/Fonts/STSong.ttc'))
pdfmetrics.registerFont(TTFont('SimHei', '/System/Library/Fonts/STHeiti Light.ttc'))

doc = SimpleDocTemplate("chinese.pdf", pagesize=A4)
styles = getSampleStyleSheet()

# 创建中文字体样式
style = ParagraphStyle(
    name='Chinese',
    fontName='SimSun',
    fontSize=12,
    leading=20
)

story = []
story.append(Paragraph("中文测试文档", styles['Title']))
story.append(Spacer(1, 12))
story.append(Paragraph("这是一段中文内容。", style))

doc.build(story)
```

### Unicode上标下标警告

**禁止使用Unicode上标/下标字符**（₀₁₂₃₄₅₆₇₈₉, ⁰¹²³⁴⁵⁶⁷⁸⁹），它们会显示为黑块。

正确做法：
```python
# ✅ 使用XML标记
chemical = Paragraph("H<sub>2</sub>O", style)  # 下标
squared = Paragraph("x<super>2</super>", style)  # 上标

# ❌ 不要使用Unicode字符
# chemical = Paragraph("H₂O", style)  # 会显示为黑块
```

## 水印与密码保护

### 添加水印

```python
from pypdf import PdfReader, PdfWriter

watermark = PdfReader("watermark.pdf").pages[0]
reader = PdfReader("document.pdf")
writer = PdfWriter()

for page in reader.pages:
    page.merge_page(watermark)
    writer.add_page(page)

with open("watermarked.pdf", "wb") as output:
    writer.write(output)
```

### 密码保护

```python
from pypdf import PdfReader, PdfWriter

reader = PdfReader("input.pdf")
writer = PdfWriter()

for page in reader.pages:
    writer.add_page(page)

# 添加密码
writer.encrypt("user_password", "owner_password")

with open("encrypted.pdf", "wb") as output:
    writer.write(output)
```

## 输出格式规范

### 中文文档分析输出结构

当用户上传PDF并要求分析时，使用以下输出格式：

```
【文档基本信息】
- 文件名：xxx.pdf
- 页数：N页
- 提取方式：文本提取/OCR识别

【文档主题】
一句话概括文档核心内容

【核心内容摘要】
按照文档章节结构，提取关键信息：
1. 第一部分：...
2. 第二部分：...


【重要数据/指标】
- 指标1：数值
- 指标2：数值

【表格数据】
[如提取到表格，展示表格内容]

【风险/限制/注意事项】
- 识别到的数据质量问题
- 提取不完整的部分
- 需要人工核实的内容

【后续建议】
- 可以追问的问题
- 需要补充的数据
```

### 表格提取输出

当提取PDF表格时，优先导出为Excel格式：

```
【提取结果】
成功从PDF中提取了N个表格。

表格概览：
- 表格1（第X页）：行数N，列数M
- 表格2（第Y页）：行数N，列数M

详细数据已保存至：[文件名].xlsx
```

## 常见问题处理

### 问题：文本提取为空白
- 检查是否为扫描件（需要OCR）
- 尝试使用`pdfplumber`代替`pypdf`
- 检查PDF是否加密

### 问题：表格提取错位
- 调整`table_settings`参数
- 尝试设置`explicit_vertical_lines`
- 对于复杂表格，考虑手动记录关键数据

### 问题：中文显示乱码
- reportlab需要注册中文字体
- 检查系统是否安装了中文字体
- macOS推荐使用系统字体：`/System/Library/Fonts/STSong.ttc`
