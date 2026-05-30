---
name: xlsx-enhanced
description: 专业的Excel和CSV数据处理技能，支持公式创建、数据分析、格式化、财务模型构建和可视化。当用户提到Excel、数据分析、表格处理、公式计算、图表制作、财务模型等操作时使用此技能。
file_types: [.xlsx, .xlsm, .csv, .tsv]
intents: [excel, 数据分析, 表格, 公式, 计算, 图表, 财务模型, 透视表, 汇总, csv, 指标分析]
priority: 90
enabled: true
license: Based on Anthropic official XLSX skill
---

# Excel/CSV数据处理技能（增强版）

本技能整合Anthropic官方XLSX技能最佳实践，专为中文数据场景优化。

## 核心原则

### ⚠️ 最重要规则：使用公式，而非硬编码值

**必须使用Excel公式，让Excel自己计算，不要在Python中计算后硬编码值。**

```python
# ❌ 错误：Python计算后硬编码
total = df['Sales'].sum()
sheet['B10'] = total  # 硬编码了5000

growth = (df.iloc[-1]['Revenue'] - df.iloc[0]['Revenue']) / df.iloc[0]['Revenue']
sheet['C5'] = growth  # 硬编码了0.15

# ✅ 正确：使用Excel公式
sheet['B10'] = '=SUM(B2:B9)'
sheet['C5'] = '=(C4-C2)/C2'
```

## 核心库选择

| 任务 | 推荐库 | 说明 |
|------|--------|------|
| 数据分析/读取 | `pandas` | 性能好，适合数据操作 |
| 公式/格式化 | `openpyxl` | 保留公式和格式 |
| 数据写入 | `pandas` 或 `openpyxl` | 根据场景选择 |

## 读取和分析数据

### 使用pandas读取

```python
import pandas as pd

# 读取Excel（默认第一个工作表）
df = pd.read_excel('file.xlsx')

# 读取所有工作表
all_sheets = pd.read_excel('file.xlsx', sheet_name=None)

# 指定工作表
df = pd.read_excel('file.xlsx', sheet_name='Sheet1')

# 分析数据
df.head()      # 预览前几行
df.info()      # 列信息
df.describe()  # 统计摘要

# 数据类型指定
df = pd.read_excel('file.xlsx', dtype={'id': str, '日期': str})
```

### 使用openpyxl读取

```python
from openpyxl import load_workbook

# 读取Excel（保留公式）
wb = load_workbook('file.xlsx')
sheet = wb.active

# 读取计算后的值（data_only=True）
wb_data = load_workbook('file.xlsx', data_only=True)
sheet_data = wb_data.active
value = sheet_data['A1'].value

# ⚠️ 警告：使用data_only=True保存会丢失公式！
```

## 创建和编辑Excel

### 创建新Excel

```python
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side

wb = Workbook()
sheet = wb.active
sheet.title = '数据表'

# 添加数据
sheet['A1'] = '指标'
sheet['B1'] = '数值'
sheet['A2'] = '销售额'
sheet['B2'] = 50000

# 添加公式（✅ 正确方式）
sheet['C1'] = '总计'
sheet['C2'] = '=SUM(B2:B100)'

# 格式化
sheet['A1'].font = Font(bold=True, color='FF0000')
sheet['A1'].fill = PatternFill('solid', fgColor='FFFF00')
sheet['A1'].alignment = Alignment(horizontal='center')

# 列宽
sheet.column_dimensions['A'].width = 15
sheet.column_dimensions['B'].width = 12

# 保存
wb.save('output.xlsx')
```

### 编辑现有Excel

```python
from openpyxl import load_workbook

# 加载现有文件
wb = load_workbook('existing.xlsx')
sheet = wb.active

# 修改单元格
sheet['A1'] = '新值'
sheet.insert_rows(2)  # 在第2行插入
sheet.delete_cols(3)  # 删除第3列

# 添加新工作表
new_sheet = wb.create_sheet('新工作表')

# 保存
wb.save('modified.xlsx')
```

## 公式使用规范

### Excel公式重算

openpyxl创建的公式不会自动计算值！需要重算：

```python
# 方法1：使用openpyxl的数据模式重算（简单情况）
wb = load_workbook('output.xlsx')
for sheet in wb.worksheets:
    for row in sheet.iter_rows():
        for cell in row:
            if cell.data_type == 'f':  # 公式类型
                # 触发重算
                pass
wb.save('output.xlsx')

# 方法2：使用pandas导出触发重算
df.to_excel('output.xlsx', index=False)

# 方法3：使用xlwings（需要Excel安装）
# import xlwings as xw
# wb = xw.Book('output.xlsx')
# wb.app.calculate()
# wb.save()
```

### 公式验证检查清单

- ✅ 测试2-3个样本引用是否正确
- ✅ 确认列映射（Excel第64列=BL）
- ✅ 记住Excel行从1开始（DataFrame第5行=Excel第6行）
- ✅ 检查NaN值处理
- ✅ 避免除以零（#DIV/0!错误）
- ✅ 验证所有单元格引用正确

### 常见公式示例

```python
# 求和
sheet['B10'] = '=SUM(B2:B9)'

# 平均值
sheet['C5'] = '=AVERAGE(C2:C9)'

# 条件求和
sheet['D10'] = '=SUMIF(A:A,"销售额",B:B)'

# 增长率（正确写法）
sheet['C5'] = '=(C4-C2)/C2'

# 跨工作表引用
sheet['A1'] = '=Sheet1!B2'

# VLOOKUP（中文Excel使用VLOOKUP，英文使用VLOOKUP）
sheet['C2'] = '=VLOOKUP(B2,Sheet2!A:C,3,FALSE)'

# IF条件
sheet['D2'] = '=IF(B2>100,"高","低")'
```

## 数字格式化规范

### 中文场景常用格式

```python
from openpyxl.styles import numbers

# 数字格式示例
cell.number_format = '0'           # 整数
cell.number_format = '0.00'        # 2位小数
cell.number_format = '#,##0'      # 千分位
cell.number_format = '#,##0.00'    # 千分位+2位小数
cell.number_format = '¥#,##0'     # 人民币
cell.number_format = '$#,##0'     # 美元
cell.number_format = '0%'          # 百分比
cell.number_format = '0.0%'        # 1位小数百分比
cell.number_format = '0.0x'        # 倍数（EV/EBITDA等）
cell.number_format = 'yyyy-mm-dd'  # 日期
cell.number_format = 'yyyy年mm月dd日'  # 中文日期
```

### 数字格式化规则

- **年份**：格式化为文本（如"2024"而非"2,024"）
- **货币**：使用`$#,##0`格式，**始终在表头注明单位**（如"收入（万元）"）
- **零值**：使用格式化让零显示为"-"（如`$#,##0;($#,##0);-`）
- **负数**：使用括号表示（如`(123)`而非`-123`）
- **百分比**：默认1位小数（如`0.0%`）
- **倍数**：格式化为`0.0x`（如EV/EBITDA、P/E等估值倍数）

## 金融模型配色规范

### 行业标准配色

| 用途 | RGB颜色 | 说明 |
|------|---------|------|
| 蓝色文字 | 0, 0, 255 | 硬编码输入值，用户可修改 |
| 黑色文字 | 0, 0, 0 | 所有公式和计算 |
| 绿色文字 | 0, 128, 0 | 跨工作表链接 |
| 红色文字 | 255, 0, 0 | 外部文件链接 |
| 黄色背景 | 255, 255, 0 | 需要关注的假设或待更新单元格 |

### 财务模型示例

```python
from openpyxl.styles import Font

# 输入项（蓝色）
input_cell = sheet['B5']
input_cell.value = 5000000
input_cell.font = Font(color='0000FF')  # 蓝色

# 公式（黑色）
formula_cell = sheet['C5']
formula_cell.value = '=B5*1.1'
formula_cell.font = Font(color='000000')  # 黑色

# 假设项（黄色背景）
assumption_cell = sheet['B6']
assumption_cell.value = 0.1
assumption_cell.fill = PatternFill('solid', fgColor='FFFF00')  # 黄色背景
```

## 数据分析输出格式

### 中文数据分析报告结构

当用户上传Excel/CSV并要求分析时，使用以下输出格式：

```
【数据概览】
- 数据源：xxx.xlsx
- 总行数：N行
- 总列数：M列
- 列名：['列1', '列2', ...]

【数据口径】
- 每一行代表：xxx（如：一次交易、一个用户、一次访问）
- 主要维度：xxx
- 主要指标：xxx

【核心发现】
1. 整体指标：
   - 总销售额/总量：xxx
   - 平均值：xxx
   - 最大/最小值：xxx

2. 分组分析：
   按[维度]分组的关键指标对比
   | 维度 | 指标1 | 指标2 |
   |------|------|------|
   | A | xxx | xxx |

3. 趋势分析：
   [时间维度]的趋势变化

【数据质量问题】
- 缺失值：xxx
- 重复记录：xxx
- 异常值：xxx（如有）
- 单位不一致：xxx（如有）

【建议动作】
1. xxx
2. xxx

【需要补充的数据】
- xxx
```

### 表格展示格式

使用Markdown表格清晰展示数据：

```
| 渠道 | 2024年1月 | 2024年2月 | 环比变化 |
|------|----------|----------|--------|
| 线上 | 100万 | 120万 | +20% |
| 线下 | 80万 | 85万 | +6.3% |
| **合计** | **180万** | **205万** | **+13.9%** |
```

## 图表制作

### 使用openpyxl创建图表

```python
from openpyxl.chart import BarChart, LineChart, PieChart, Reference

# 柱状图
chart = BarChart()
chart.title = "月度销售对比"
chart.y_axis.title = '销售额'
chart.x_axis.title = '月份'

data = Reference(sheet, min_col=2, min_row=1, max_col=3, max_row=12)
cats = Reference(sheet, min_col=1, min_row=2, max_row=12)
chart.add_data(data, titles_from_data=True)
chart.set_categories(cats)

sheet.add_chart(chart, "E2")
```

### 使用pandas + matplotlib导出图表

```python
import pandas as pd
import matplotlib.pyplot as plt

# 设置中文字体
plt.rcParams['font.sans-serif'] = ['SimHei', 'STSong']
plt.rcParams['axes.unicode_minus'] = False

# 创建图表
df.plot(kind='bar', x='月份', y='销售额')
plt.title('月度销售对比')
plt.xlabel('月份')
plt.ylabel('销售额')

# 保存图片
plt.savefig('chart.png', dpi=300, bbox_inches='tight')
plt.close()

# 在Excel中插入图片
from openpyxl.drawing.image import Image
img = Image('chart.png')
sheet.add_image(img, 'E2')
```

## 常见问题处理

### 问题：公式不计算
- openpyxl创建的公式需要重算
- 检查是否使用了`data_only=True`读取（这会丢失公式）
- 验证公式语法是否正确

### 问题：数字格式不正确
- 检查number_format设置
- 中文Excel和英文Excel的格式代码可能不同
- 日期格式特别注意

### 问题：中文显示乱码
- 检查系统字体是否正确
- matplotlib需要单独设置中文字体
- Excel本身支持中文一般没问题

### 问题：CSV读取乱码
- 尝试不同编码：`pd.read_csv('file.csv', encoding='utf-8')`
- 常见中文编码：`gbk`, `gb18030`, `utf-8-sig`
- 使用`encoding='utf-8-sig'`处理带BOM的UTF-8
