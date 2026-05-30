---
name: docx-enhanced
description: 专业的Word文档处理技能，支持创建、编辑、追踪修订和格式化。当用户提到Word、文档、创建文档、编辑文档、docx、审阅文档等操作时使用此技能。
file_types: [.docx]
intents: [word, 文档, docx, 创建文档, 编辑文档, 审阅, 修订, 追踪修订, 报告, 合同]
priority: 80
enabled: true
license: Based on Anthropic official DOCX skill
---

# Word文档技能（增强版）

本技能整合Anthropic官方DOCX技能最佳实践，专为中文文档场景优化。

## 工作流程决策树

### 阅读/分析内容
使用文本提取或原始XML访问

### 创建新文档
使用python-docx或docx-js创建

### 编辑现有文档
- **简单修改**：使用基础OOXML编辑
- **审阅他人文档**：使用**追踪修订工作流**（推荐默认）
- **法律/学术/政府文档**：使用**追踪修订工作流**（必须）

## 读取和分析文档

### 文本提取（推荐）

使用pandoc转换为markdown：

```bash
# 安装pandoc
# macOS: brew install pandoc
# Ubuntu: sudo apt-get install pandoc

# 转换为markdown（保留追踪修订）
pandoc --track-changes=all document.docx -o output.md

# 选项: --track-changes=accept/reject/all
```

### 使用python-docx读取

```python
from docx import Document

doc = Document('document.docx')

# 读取所有段落
for para in doc.paragraphs:
    print(para.text)

# 读取所有表格
for table in doc.tables:
    for row in table.rows:
        row_data = [cell.text for cell in row.cells]
        print(row_data)

# 读取文档结构
headings = []
for para in doc.paragraphs:
    if para.style.name.startswith('Heading'):
        headings.append((para.style.name, para.text))

# 统计文档基本信息
print(f"段落数: {len(doc.paragraphs)}")
print(f"表格数: {len(doc.tables)}")
print(f"图片数: {len(doc.inline_shapes)}")
```

## 创建新文档

### 使用python-docx创建

```python
from docx import Document
from docx.shared import Pt, RGBColor, Inches
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.style import WD_STYLE_TYPE

# 创建文档
doc = Document()

# 添加标题
title = doc.add_heading('文档标题', level=0)
title.alignment = WD_ALIGN_PARAGRAPH.CENTER

# 添加段落
para = doc.add_paragraph()
para.add_run('这是').bold = False
para.add_run('加粗文本').bold = True
para.add_run('和普通文本').bold = False

# 添加带格式的文本
run = para.add_run('蓝色文本')
run.font.color.rgb = RGBColor(0, 0, 255)
run.font.size = Pt(12)

# 添加项目符号列表
doc.add_paragraph('第一点', style='List Bullet')
doc.add_paragraph('第二点', style='List Bullet')
doc.add_paragraph('第三点', style='List Bullet')

# 添加编号列表
doc.add_paragraph('第一步', style='List Number')
doc.add_paragraph('第二步', style='List Number')

# 添加表格
table = doc.add_table(rows=3, cols=3)
table.style = 'Light Grid Accent 1'

# 填充表格
header_cells = table.rows[0].cells
header_cells[0].text = '姓名'
header_cells[1].text = '年龄'
header_cells[2].text = '城市'

# 添加行
row_cells = table.add_row().cells
row_cells[0].text = '张三'
row_cells[1].text = '25'
row_cells[2].text = '北京'

# 添加分页
doc.add_page_break()

# 添加第二部分
doc.add_heading('第二部分', level=1)

# 保存
doc.save('output.docx')
```

### 中文字体设置

```python
from docx.oxml.ns import qn

# 设置中文字体（针对整个文档）
doc.styles['Normal'].font.name = '宋体'
doc.styles['Normal']._element.rPr.rFonts.set(qn('w:eastAsia'), '宋体')

# 设置标题字体
for i in range(1, 4):
    style = doc.styles[f'Heading {i}']
    style.font.name = '黑体'
    style._element.rPr.rFonts.set(qn('w:eastAsia'), '黑体')
    style.font.size = Pt(16 if i == 1 else 14)
    style.font.bold = True
```

## 编辑现有文档

### 简单编辑

```python
from docx import Document

doc = Document('existing.docx')

# 查找并替换文本
for para in doc.paragraphs:
    if '旧文本' in para.text:
        para.text = para.text.replace('旧文本', '新文本')

# 修改表格
for table in doc.tables:
    for row in table.rows:
        for cell in row.cells:
            if '要替换' in cell.text:
                cell.text = cell.text.replace('要替换', '替换为')

# 添加新内容
doc.add_paragraph('新增段落', style='Heading 2')

# 保存
doc.save('modified.docx')
```

### 复杂编辑（OOXML级别）

当需要处理复杂格式时，需要直接操作XML：

```python
from docx import Document
from docx.oxml import parse_xml
from docx.oxml.ns import qn

doc = Document('document.docx')

# 访问底层XML
for para in doc.paragraphs:
    # 获取段落的XML元素
    p = para._element

    # 添加加粗和着色
    run = para.add_run('新文本')
    run.bold = True
    run.font.color.rgb = RGBColor(255, 0, 0)

    # 修改样式
    rPr = run._element.get_or_add_rPr()
    rPr.set(qn('w:highlight'), 'yellow')  # 高亮

doc.save('modified.docx')
```

## 追踪修订工作流

当审阅他人文档或进行多人协作时，使用追踪修订模式。

### 工作流程

1. **获取markdown表示**：
   ```bash
   pandoc --track-changes=all document.docx -o current.md
   ```

2. **识别和组织变更**：审查文档并组织所有需要的变更

3. **实施变更**：按照批处理策略实施变更

4. **打包文档**：
   ```bash
   # 如有打包脚本
   python pack.py unpacked modified.docx
   ```

5. **最终验证**

### 批处理策略

将相关变更分组为3-10个一批，便于调试：

**按文档部分分组**：
- Batch 1: 第一章修订
- Batch 2: 第二章修订

**按变更类型分组**：
- Batch 1: 日期更正
- Batch 2: 名称更新
- Batch 3: 条款修改

**按位置分组**：
- Batch 1: 第1-3页
- Batch 2: 第4-6页

### 变更实现原则

**原则：最小化精确编辑**

只标记实际变更的文本。拆分替换为：`[未变更文本] + [删除] + [插入] + [未变更文本]`

**示例**：将"30天"改为"60天"

```python
# ❌ 错误：替换整个句子
'<w:del><w:r><w:delText>合同期限为30天。</w:delText></w:r></w:del><w:ins><w:r><w:t>合同期限为60天。</w:t></w:r></w:ins>'

# ✅ 正确：只标记变更部分
'<w:r><w:t>合同期限为</w:t></w:r><w:del><w:r><w:delText>30</w:delText></w:r></w:del><w:ins><w:r><w:t>60</w:t></w:r></w:ins><w:r><w:t>天。</w:t></w:r>'
```

## 文档转换

### 转换为图片（视觉分析）

```bash
# 1. 转换为PDF
soffice --headless --convert-to pdf document.docx

# 2. PDF转换为图片
pdftoppm -jpeg -r 150 document.pdf page
```

### 转换为其他格式

```bash
# 转换为HTML
pandoc document.docx -o output.html

# 转换为Markdown
pandoc document.docx -o output.md

# 转换为PDF
pandoc document.docx -o output.pdf
```

## 中文文档输出格式

### 分析文档

当用户上传Word文档并要求分析时：

```
【文档概览】
- 文件名：xxx.docx
- 段落数：N个
- 表格数：M个
- 图片数：K个

【文档结构】
使用层级标题组织的内容摘要

【核心内容】
按照章节结构提取关键信息：
1. 第一章：xxx
   - 主要观点：xxx
   - 关键数据：xxx
   - 行动项：xxx

2. 第二章：xxx
   ...

【关键事实与证据】
- 关键数据1：xxx
- 关键数据2：xxx
- 证据来源：xxx

【风险/限制/待确认】
- 分歧点：xxx
- 未明确事项：xxx
- 需要核实的内容：xxx

【行动项和责任】
- 行动项1：[负责人]负责[事项]
- 行动项2：[负责人]负责[事项]

【后续建议】
- 可以追问的问题
- 需要补充的数据
```

### 创建文档

当用户要求创建文档时：

```
【文档创建计划】
我将为您创建以下结构的文档：

**文档类型**：xxx（如：报告、合同、方案）

**结构设计**：
1. 封面/标题
2. 目录
3. 第一部分：xxx
4. 第二部分：xxx
5. 附件（如有）

**格式规范**：
- 标题层级：使用[标题样式]
- 正文字体：[字体]，[字号]
- 行距：1.5倍行距
- 页边距：上下2.54厘米，左右3.17厘米

**预计内容长度**：约X页

是否需要调整文档结构或内容方向？
```

## 常见问题处理

### 问题：文档格式错乱
- 检查是否使用了不兼容的字体
- 确保使用docx标准格式
- 避免在文本中直接使用特殊字符

### 问题：中文字体显示问题
- 明确指定中文字体（宋体、黑体、楷体等）
- 设置`font.name`和`eastAsia`字体
- 避免使用仅英文的字体

### 问题：表格错位
- 使用固定列宽：`table.columns[0].width = Inches(2)`
- 避免表格跨页断行
- 合并单元格时注意对齐

### 问题：追踪修订不生效
- 确保文档处于修订模式
- 检查XML中的`<w:ins>`和`<w:del>`标签
- 验证RSID（修订标识符）正确

## 依赖库安装

```bash
# 基础库
pip install python-docx

# 文档转换
pip install pandoc

# XML处理（安全）
pip install defusedxml

# PDF转换
# macOS: brew install libreoffice
# Ubuntu: sudo apt-get install libreoffice
```
