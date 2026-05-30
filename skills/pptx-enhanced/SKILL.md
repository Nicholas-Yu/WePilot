---
name: pptx-enhanced
description: 专业的PPT幻灯片处理技能，支持创建、编辑、设计和视觉优化。当用户提到PPT、幻灯片、演示文稿、创建PPT、编辑PPT、设计建议等操作时使用此技能。
file_types: [.pptx]
intents: [ppt, pptx, 幻灯片, 演示, 汇报, 创建ppt, 制作ppt, deck, slide, 页面, 讲稿]
priority: 85
enabled: true
license: Based on Anthropic official PPTX skill
---

# PowerPoint演示文稿技能（增强版）

本技能整合Anthropic官方PPTX技能最佳实践，专为中文演示场景优化。

## 快速参考

| 任务 | 工具/方法 |
|------|----------|
| 读取/分析内容 | `python -m markitdown presentation.pptx` |
| 从模板编辑 | 见编辑工作流程 |
| 从零创建 | 使用pptxgenjs或python-pptx |

## 读取PPT内容

### 文本提取

```bash
# 安装markitdown
pip install "markitdown[pptx]"

# 提取文本
python -m markitdown presentation.pptx
```

### 缩略图预览

```python
# 使用python-pptx创建缩略图
from pptx import Presentation
from pptx.util import Inches, Pt

prs = Presentation('presentation.pptx')
for i, slide in enumerate(prs.slides):
    # 保存为图片（需要额外处理）
    pass
```

### 提取演讲者备注

```python
from pptx import Presentation

prs = Presentation('presentation.pptx')
for i, slide in enumerate(prs.slides):
    if slide.has_notes_slide:
        notes_slide = slide.notes_slide
        notes_text = notes_slide.notes_text_frame.text
        print(f"第{i+1}页备注: {notes_text}")
```

## 设计原则

### ⚠️ 重要：不要创建无聊的幻灯片！

plain文字+白背景的幻灯片无法给人留下深刻印象。

### 设计前准备

1. **选择配色方案**：选择适合主题的配色，不要默认使用通用蓝色
2. **主次分明**：一个颜色应占据主导地位（60-70%视觉权重），配1-2个辅助色和1个强调色
3. **明暗对比**：标题页和结尾页使用深色背景，内容页使用浅色背景（"三明治"结构）
4. **视觉主题**：选择一个独特的视觉元素并重复使用

### 配色方案推荐

适合中文商务场景的配色：

| 主题 | 主色 | 辅助色 | 强调色 | 适用场景 |
|------|------|--------|--------|----------|
| **商务经典** | 1E2761（深蓝） | CADCFC（冰蓝） | FFFFFF（白） | 正式汇报 |
| **活力创新** | F96167（珊瑚） | F9E795（金） | 2F3C7E（藏青） | 创业路演 |
| **专业稳重** | 36454F（炭灰） | F2F2F2（浅灰） | 212121（黑） | 企业内训 |
| **清新自然** | 2C5F2D（森林） | 97BC62（苔绿） | F5F5F5（米白） | 环保主题 |
| **现代科技** | 028090（青绿） | 00A896（薄荷） | 02C39A（薄荷绿） | 科技产品 |
| **温暖亲和** | B85042（赤陶） | E7E8D1（沙色） | A7BEAE（鼠尾草） | 温暖故事 |

### 每页设计要点

**每页都需要视觉元素**——图片、图表、图标或形状，纯文字页容易被人遗忘。

### 布局选择

- **双栏布局**：文字在左，插图在右
- **图标+文字行**：图标放在彩色圆圈中，粗体标题，下方说明
- **2x2或2x3网格**：一侧是图片，另一侧是内容块
- **半出血图片**：左侧或右侧全出血，叠加内容

### 数据展示

- **大数字展示**（60-72pt大数字+小标签）
- **对比列**（前后对比、利弊对比、方案对比）
- **时间线或流程图**（编号步骤+箭头）

### 视觉优化

- 图标放在小彩色圆圈中，紧邻章节标题
- 关键数据或标语使用斜体强调文字

### 字体选择

**选择有趣的字体搭配**，不要默认使用Arial：

| 标题字体 | 正文字体 | 风格 |
|---------|---------|------|
| **中文标题** | **中文正文** | **推荐组合** |
| 黑体/微软雅黑 | 宋体/微软雅黑 | 现代商务 |
| 方正舒体 | 宋体 | 文化感 |
| 华文行楷 | 宋体 | 活泼亲切 |
| Georgia | Calibri | 经典英文 |
| Trebuchet MS | Calibri | 现代英文 |

### 字号规范

| 元素 | 字号 |
|------|------|
| 幻灯片标题 | 36-44pt 加粗 |
| 章节标题 | 20-24pt 加粗 |
| 正文 | 14-16pt |
| 备注/引用 | 10-12pt 淡化 |

### 间距规范

- 页边距至少0.5英寸
- 内容块之间0.3-0.5英寸
- 保持呼吸感——不要填满每一寸空间

## ⚠️ 常见错误避免

- **不要重复相同布局**：变化栏、卡片和callout
- **不要居中对齐正文**：段落和列表左对齐；只对标题居中
- **字号对比要明显**：标题需要36pt+才能从14-16pt正文中突出
- **不要默认蓝色**：选择反映特定主题的颜色
- **不要随意混用间距**：选择0.3"或0.5"的间距并一致使用
- **不要只设计一页**：要么全套风格统一，要么保持简单
- **不要创建纯文字页**：添加图片、图标、图表或视觉元素
- **不要忘记文本框内边距**：对齐线条或形状时，设置`margin: 0`
- **避免低对比度**：图标和文字都需要与背景强对比

## 创建PPT

### 使用python-pptx创建

```python
from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.dml.color import RgbColor
from pptx.enum.text import PP_ALIGN

# 创建演示文稿
prs = Presentation()
prs.slide_width = Inches(10)
prs.slide_height = Inches(7.5)

# 添加幻灯片（空白布局）
blank_layout = prs.slide_layouts[6]
slide = prs.slides.add_slide(blank_layout)

# 添加标题
title_box = slide.shapes.add_textbox(Inches(0.5), Inches(0.5), Inches(9), Inches(1))
title_frame = title_box.text_frame
title_para = title_frame.paragraphs[0]
title_para.text = "演示文稿标题"
title_para.font.size = Pt(44)
title_para.font.bold = True
title_para.alignment = PP_ALIGN.CENTER

# 添加内容
content_box = slide.shapes.add_textbox(Inches(0.5), Inches(2), Inches(9), Inches(4))
content_frame = content_box.text_frame
content_para = content_frame.paragraphs[0]
content_para.text = "第一点内容"
content_para.font.size = Pt(20)

# 添加第二点
content_para2 = content_frame.add_paragraph()
content_para2.text = "第二点内容"
content_para2.font.size = Pt(20)

# 保存
prs.save('output.pptx')
```

### 使用pptxgenjs创建（Node.js）

pptxgenjs更适合复杂设计，但需要Node.js环境：

```javascript
const pptxgen = require("pptxgenjs");
let pres = new pptxgen();
pres.layout = 'LAYOUT_16x9';
pres.author = 'Your Name';
pres.title = '演示文稿标题';

let slide = pres.addSlide();

// 标题
slide.addText("演示文稿标题", {
  x: 0.5, y: 0.5, w: 9, h: 1,
  fontSize: 44, bold: true, color: "1E2761"
});

// 内容
slide.addText([
  { text: "第一点内容", options: { bullet: true, breakLine: true } },
  { text: "第二点内容", options: { bullet: true } }
], {
  x: 0.5, y: 2, w: 9, h: 3,
  fontSize: 20, color: "363636"
});

pres.writeFile({ fileName: "output.pptx" });
```

## 编辑现有PPT

### 编辑工作流程

1. **分析模板**：
   ```bash
   python -m markitdown template.pptx  # 提取文本
   # 生成缩略图
   ```

2. **规划幻灯片映射**：为每个内容部分选择模板幻灯片
   - ⚠️ **使用多样化布局**！
   - 不要默认使用基本标题+项目符号

3. **解包PPT**：
   ```bash
   # 如有解包脚本
   python unpack.py template.pptx unpacked/
   ```

4. **编辑内容**：更新每个slide{N}.xml中的文本

5. **打包PPT**

### 编辑示例

```python
from pptx import Presentation

# 加载PPT
prs = Presentation('existing.pptx')

# 获取第一张幻灯片
slide = prs.slides[0]

# 修改标题
if slide.shapes.title:
    slide.shapes.title.text = "新标题"

# 修改正文
for shape in slide.shapes:
    if shape.has_text_frame:
        for paragraph in shape.text_frame.paragraphs:
            for run in paragraph.runs:
                if "要替换的文本" in run.text:
                    run.text = run.text.replace("要替换的文本", "新文本")

# 添加新幻灯片
blank_layout = prs.slide_layouts[6]
new_slide = prs.slides.add_slide(blank_layout)

# 保存
prs.save('modified.pptx')
```

## 图表制作

### 在PPT中插入图表

```python
from pptx import Presentation
from pptx.chart.data import CategoryChartData
from pptx.enum.chart import XL_CHART_TYPE

prs = Presentation()
slide = prs.slides.add_slide(prs.slide_layouts[5])

# 添加图表
chart_data = CategoryChartData()
chart_data.categories = ['一月', '二月', '三月', '四月']
chart_data.add_series('销售额', (100, 120, 140, 180))

x, y, cx, cy = Inches(1), Inches(1.5), Inches(8), Inches(4.5)
chart = slide.shapes.add_chart(
    XL_CHART_TYPE.COLUMN_CLUSTERED, x, y, cx, cy, chart_data
).chart

# 设置图表标题
chart.has_title = True
chart.chart_title.text_frame.text = "季度销售趋势"

# 保存
prs.save('chart.pptx')
```

## 质量检查（QA）

### ⚠️ 重要：假设有问题！你的工作是找到它们。

第一次渲染几乎不可能完全正确。将QA视为寻找bug，而不是确认步骤。

### 内容检查

```bash
# 提取文本检查
python -m markitdown output.pptx

# 检查是否有占位符文本
python -m markitdown output.pptx | grep -iE "xxxx|lorem|ipsum|placeholder"
```

### 视觉检查

将幻灯片转换为图片进行目视检查：

1. 转换为PDF：
   ```bash
   # 使用LibreOffice
   soffice --headless --convert-to pdf output.pptx
   ```

2. 转换为图片：
   ```bash
   # 使用ImageMagick
   convert -density 150 output.pdf slide-%02d.jpg

   # 或使用pdftoppm
   pdftoppm -jpeg -r 150 output.pdf slide
   ```

3. 目视检查：
   - 检查是否有重叠元素
   - 检查文字是否溢出或被裁剪
   - 检查间距是否均匀
   - 检查边距是否足够（至少0.5英寸）
   - 检查对齐是否一致
   - 检查对比度是否足够

## 中文PPT输出格式

### 分析现有PPT

当用户上传PPT并要求分析时：

```
【演示文稿概览】
- 文件名：xxx.pptx
- 总页数：N页
- 尺寸：16:9 / 4:3

【整体叙事结构】
描述演示的逻辑主线和故事线

【逐页分析】
第1页：标题页
- 内容：xxx
- 视觉元素：xxx
- 关键信息：xxx

第2页：内容页
- 主要观点：xxx
- 支持论据：xxx
- 视觉呈现：xxx

...

【核心数据和论据】
- 关键数据1：xxx
- 关键数据2：xxx
- 核心论据：xxx

【逻辑风险或缺口】
- 识别到的逻辑问题
- 证据不足的地方
- 论证薄弱环节

【汇报建议】
- 演讲开场建议
- 重点强调内容
- 时间控制建议

【可复用话术】
- 关键转折语
- 总结语
```

### 创建新PPT

当用户要求创建PPT时：

```
【创建计划】
我将为您的演示文稿创建以下结构：

**配色方案**：选择了[配色名称]，适合[主题]

**幻灯片结构**：
1. 封面页
2. 目录页
3. 第一章节：xxx
4. 第二章节：xxx
5. 总结页

**设计亮点**：
- 采用了三明治结构（深色封面+浅色内容+深色结尾）
- 关键数据使用大字号突出展示
- 使用了图标增强视觉层次

是否需要调整任何部分？
```

## 依赖库安装

```bash
# 基础库
pip install python-pptx

# 文本提取（可选）
pip install "markitdown[pptx]"

# 如果使用Node.js
npm install pptxgenjs
```
