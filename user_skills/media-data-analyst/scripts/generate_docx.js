const { Document, Packer, Paragraph, TextRun, Table, TableRow, TableCell, 
        Header, Footer, AlignmentType, PageOrientation, LevelFormat,
        HeadingLevel, BorderStyle, WidthType, ShadingType,
        VerticalAlign, PageNumber, PageBreak } = require('docx');
const fs = require('fs');

// 统计数据
const stats = [
    { platform: '抖音', count: 9, reads: 129762, likes: 5060, comments: 114, shares: 38, favs: 247, interacts: 5459, rate: '4.21%' },
    { platform: '公众号', count: 20, reads: 1699, likes: 21, comments: 0, shares: 79, favs: 0, interacts: 112, rate: '6.59%' },
    { platform: '今日头条', count: 8, reads: 1140, likes: 19, comments: 0, shares: 6, favs: 3, interacts: 28, rate: '2.46%' },
    { platform: '视频号', count: 11, reads: 0, likes: 484, comments: 31, shares: 0, favs: 459, interacts: 1978, rate: 'N/A' },
    { platform: '微博', count: 16, reads: 0, likes: 90, comments: 37, shares: 0, favs: 0, interacts: 181, rate: 'N/A' },
    { platform: '客户端', count: 3, reads: 278046, likes: 656, comments: 145, shares: 844, favs: 0, interacts: 1645, rate: '0.63%' }
];

// 表格边框样式
const border = { style: BorderStyle.SINGLE, size: 1, color: "CCCCCC" };
const borders = { top: border, bottom: border, left: border, right: border };

// 创建表格单元格
function createCell(text, isHeader = false, width = 1200) {
    return new TableCell({
        borders,
        width: { size: width, type: WidthType.DXA },
        shading: isHeader ? { fill: "2C3E50", type: ShadingType.CLEAR } : undefined,
        margins: { top: 60, bottom: 60, left: 80, right: 80 },
        verticalAlign: VerticalAlign.CENTER,
        children: [new Paragraph({
            alignment: AlignmentType.CENTER,
            children: [new TextRun({ 
                text: text, 
                bold: isHeader, 
                color: isHeader ? "FFFFFF" : "333333",
                size: 20,
                font: { ascii: "Arial", hAnsi: "Arial", eastAsia: "Microsoft YaHei" }
            })]
        })]
    });
}

// 创建数据行
function createDataRow(data) {
    return new TableRow({
        cantSplit: true,
        children: [
            createCell(data.platform, false, 1200),
            createCell(String(data.count), false, 1000),
            createCell(data.reads ? String(data.reads) : '-', false, 1200),
            createCell(String(data.likes), false, 1000),
            createCell(String(data.comments), false, 800),
            createCell(String(data.shares), false, 800),
            createCell(String(data.favs), false, 800),
            createCell(String(data.interacts), false, 1000),
            createCell(data.rate, false, 1000)
        ]
    });
}

// 辅助函数：创建文本段落
function createText(text) {
    return new TextRun({ text: text, font: { ascii: "Arial", hAnsi: "Arial", eastAsia: "Microsoft YaHei" } });
}

function createBold(text) {
    return new TextRun({ text: text, bold: true, font: { ascii: "Arial", hAnsi: "Arial", eastAsia: "Microsoft YaHei" } });
}

// 创建文档
const doc = new Document({
    styles: {
        default: {
            document: {
                run: {
                    font: { ascii: "Arial", hAnsi: "Arial", eastAsia: "Microsoft YaHei" },
                    size: 24
                }
            }
        },
        paragraphStyles: [
            { id: "Heading1", name: "Heading 1", basedOn: "Normal", next: "Normal", quickFormat: true,
              run: { size: 36, bold: true, color: "1E3A5F", font: { ascii: "Arial", hAnsi: "Arial", eastAsia: "Microsoft YaHei" } },
              paragraph: { spacing: { before: 400, after: 200 }, outlineLevel: 0, keepNext: false, keepLines: false } },
            { id: "Heading2", name: "Heading 2", basedOn: "Normal", next: "Normal", quickFormat: true,
              run: { size: 28, bold: true, color: "2C3E50", font: { ascii: "Arial", hAnsi: "Arial", eastAsia: "Microsoft YaHei" } },
              paragraph: { spacing: { before: 300, after: 150 }, outlineLevel: 1, keepNext: false, keepLines: false } },
            { id: "Heading3", name: "Heading 3", basedOn: "Normal", next: "Normal", quickFormat: true,
              run: { size: 24, bold: true, color: "34495E", font: { ascii: "Arial", hAnsi: "Arial", eastAsia: "Microsoft YaHei" } },
              paragraph: { spacing: { before: 200, after: 100 }, outlineLevel: 2, keepNext: false, keepLines: false } }
        ]
    },
    sections: [{
        properties: {
            page: {
                size: { width: 11906, height: 16838 },
                margin: { top: 1440, right: 1440, bottom: 1440, left: 1440 }
            }
        },
        headers: {
            default: new Header({
                children: [new Paragraph({
                    alignment: AlignmentType.RIGHT,
                    children: [new TextRun({ text: "潮声·青年说 预热期数据简报", size: 18, color: "999999" })]
                })]
            })
        },
        footers: {
            default: new Footer({
                children: [new Paragraph({
                    alignment: AlignmentType.CENTER,
                    children: [
                        new TextRun({ text: "第 ", size: 18 }),
                        new TextRun({ children: [PageNumber.CURRENT], size: 18 }),
                        new TextRun({ text: " 页", size: 18 })
                    ]
                })]
            })
        },
        children: [
            // 封面
            new Paragraph({ spacing: { before: 2000 } }),
            new Paragraph({
                alignment: AlignmentType.CENTER,
                children: [new TextRun({ text: "潮声·青年说", bold: true, size: 72, color: "1E3A5F" })]
            }),
            new Paragraph({ spacing: { before: 200 } }),
            new Paragraph({
                alignment: AlignmentType.CENTER,
                children: [new TextRun({ text: "项目预热期跨渠道数据与内容简报", size: 44, color: "2C3E50" })]
            }),
            new Paragraph({ spacing: { before: 600 } }),
            new Paragraph({
                alignment: AlignmentType.CENTER,
                children: [new TextRun({ text: "跨渠道数据穿透 · 算法适配度解析 · 流量漏斗归因", size: 24, color: "7F8C8D" })]
            }),
            new Paragraph({ spacing: { before: 1500 } }),
            new Paragraph({
                alignment: AlignmentType.CENTER,
                children: [new TextRun({ text: "2026年5月6日", size: 28, color: "34495E" })]
            }),
            new Paragraph({ spacing: { before: 400 } }),
            new Paragraph({
                alignment: AlignmentType.CENTER,
                children: [new TextRun({ text: "省级融媒体中心数据中台", size: 22, color: "95A5A6" })]
            }),
            
            // 分页
            new Paragraph({ children: [new PageBreak()] }),
            
            // 正文开始
            new Paragraph({
                heading: HeadingLevel.HEADING_1,
                children: [new TextRun("一、客观数据归总与洞察")]
            }),
            
            new Paragraph({
                spacing: { before: 200, after: 200 },
                children: [createText("基于预热期全网跨渠道分发的67条物料，各核心阵地大盘数据收录如下：")]
            }),
            
            // 数据表格
            new Table({
                width: { size: 100, type: WidthType.PERCENTAGE },
                columnWidths: [1200, 1000, 1200, 1000, 800, 800, 800, 1000, 1000],
                rows: [
                    new TableRow({
                        cantSplit: true,
                        children: [
                            createCell("平台矩阵", true, 1200),
                            createCell("发文数量", true, 1000),
                            createCell("预估播放/阅读", true, 1200),
                            createCell("获赞/推荐", true, 1000),
                            createCell("评论", true, 800),
                            createCell("分享/转发", true, 800),
                            createCell("收藏/喜欢", true, 800),
                            createCell("总互动量", true, 1000),
                            createCell("平均互动率", true, 1000)
                        ]
                    }),
                    ...stats.map(createDataRow)
                ]
            }),
            
            new Paragraph({ spacing: { before: 300 } }),
            
            new Paragraph({
                heading: HeadingLevel.HEADING_2,
                children: [new TextRun("【客观数据洞察】")]
            }),
            
            new Paragraph({
                spacing: { before: 150 },
                children: [
                    createBold("缺失值豁免申明："),
                    createText("受限于各平台开放平台的API接口限制及封闭社交圈层的数据黑盒特性，外部采集难以获取真实底层曝光数据（如本期微博与视频号的阅读/播放底数为空值），当前评估将以互动绝对值与互动结构（赞/转/评比例）为核心考核依据。")
                ]
            }),
            
            new Paragraph({
                spacing: { before: 150 },
                children: [
                    createBold("流量破圈尖刀：抖音。"),
                    createText("仅通过9篇发文量即撬动近13万级曝光与超5000次互动，互动率达4.21%，是当前唯一具备公域爆款潜质的核心破圈渠道。")
                ]
            }),
            
            new Paragraph({
                spacing: { before: 150 },
                children: [
                    createBold("私域裂变中枢：公众号。"),
                    createText("虽整体阅读大盘基数较小（1699次），但在评论、收藏功能受限的客观条件下，依然逆势贡献了全盘最高的单平台分享数（79次），核心宣发阵地的内部动员与私域渗透能力依然稳固。")
                ]
            }),
            
            new Paragraph({
                spacing: { before: 150 },
                children: [
                    createBold("深层互动黑马：视频号。"),
                    createText('在缺乏基础播放量支撑的劣势下，仍斩获459次极高强度的"收藏/喜欢"指标，熟人社交链的网状推荐机制正初步起效，具备极高的长尾留存价值。')
                ]
            }),
            
            // 微博话题分析
            new Paragraph({ spacing: { before: 400 } }),
            new Paragraph({
                heading: HeadingLevel.HEADING_2,
                children: [new TextRun("【微博话题专项势能洞察】")]
            }),
            
            new Paragraph({
                spacing: { before: 200, after: 200 },
                children: [createText("针对本次打通的微博热搜榜单与话题数据，为规避同话题同量级的重复统计，对底层数据进行去重合并后洞察如下：")]
            }),
            
            new Paragraph({
                spacing: { before: 150 },
                children: [createText('从微博场域的话题势能来看，矩阵联动的"集火"效应呈明显的两极分化。以核心冲榜话题为例，由')]
            }),
            new Paragraph({
                spacing: { before: 100 },
                children: [
                    new TextRun({ text: '钱江晚报主持的"#浙江日报青年主播天团上线#"话题，有浙商杂志官方微博、潮视频、浙江法治报等8个矩阵账号联袂发布，实际去重话题阅读量高达1038.9万。得益于跨账号的并发势能，该话题成功突围，在新浪微博的11个地市热搜榜单', bold: true }),
                    createText("（含绍兴、温州、宁波等同城实时搜索）上多点展现，"),
                    new TextRun({ text: "排名最高飙升至第10位", bold: true }),
                    createText("。")
                ]
            }),
            
            new Paragraph({
                spacing: { before: 150 },
                children: [createText("形成鲜明对比的是，作为基建主干话题的")]
            }),
            new Paragraph({
                spacing: { before: 100 },
                children: [
                    new TextRun({ text: '"#潮声青年说#"，在同样由钱江晚报主持、同样8个矩阵账号联动的基准下，其去重阅读量仅停留在28万量级，且未能触发任何热搜榜单的收录排名。', bold: true })
                ]
            }),
            
            new Paragraph({
                spacing: { before: 200 },
                children: [
                    createBold("【洞察结论】"),
                    createText('：这不仅验证了在微博场域利用矩阵号统一挂载主Tag集中冲榜是打破限流的有效打法，更从数据层面直接证明了"带有强烈人设感与事件冲突感的次生话题（如\'天团上线\'）"在流量获取效率上，要成十倍、百倍地碾压"干瘪呆板的栏目名主话题（如\'青年说\'）"。在下阶段的宣发中，应全面摈弃将栏目名作为冲榜主Tag的执念，将资源倾斜给事件向、人物向的话题引擎。')
                ]
            }),
            
            // 分页
            new Paragraph({ children: [new PageBreak()] }),
            
            // 第二部分
            new Paragraph({
                heading: HeadingLevel.HEADING_1,
                children: [new TextRun("二、分平台内容特征诊断")]
            }),
            
            new Paragraph({
                spacing: { before: 200, after: 200 },
                children: [createText('目前宣发链路存在极其严重的"一稿多投"顽疾，信息熵分配严重错位。各渠道文本特征及算法适配度拆解如下：')]
            }),
            
            // 公众号
            new Paragraph({
                heading: HeadingLevel.HEADING_2,
                children: [new TextRun("1. 微信公众号：缺乏C端利益钩子")]
            }),
            
            new Paragraph({
                spacing: { before: 150 },
                children: [
                    createBold("抽取样本："),
                    createText('"浙报集团年度重磅产品\'潮声·青年说\'将于5月6日闪亮登场"')
                ]
            }),
            
            new Paragraph({
                spacing: { before: 100 },
                children: [
                    createBold("【优点】："),
                    createText('格式极其规范，倒计时体例（如"1日后"）具备明确的日历提醒属性，较好地承载了矩阵号"官方公告板"的基础职能。')
                ]
            }),
            
            new Paragraph({
                spacing: { before: 100 },
                children: [
                    createBold("【缺点】："),
                    createText('"年度重磅"、"闪亮登场"等话术带有极其浓厚的To B/To G内部视角，严重缺乏针对普通C端读者的"利益钩子"（Hook），在公众号私域场域内难以击穿用户的点开防御机制。')
                ]
            }),
            
            new Paragraph({
                spacing: { before: 100 },
                children: [
                    createBold("【优化意见】："),
                    createText('强制执行视点转换，将"报业集团推出了什么"降维翻译为"读者能从中获取什么情绪或价值"。')
                ]
            }),
            
            // 微博
            new Paragraph({
                heading: HeadingLevel.HEADING_2,
                children: [new TextRun("2. 微博：学术黑话阻断网感")]
            }),
            
            new Paragraph({
                spacing: { before: 150 },
                children: [
                    createBold("抽取样本："),
                    createText('"【#浙江日报青年主播天团上线#】浙江日报报业集团推出理论融媒产品...党的创新理论传播面临\'如何走近青年..."')
                ]
            }),
            
            new Paragraph({
                spacing: { before: 100 },
                children: [
                    createBold("【优点】："),
                    createText("规范挂载双话题标签（#潮声青年说#、#浙江日报青年主播天团上线#），符合微博话题聚合与广场冲榜的基础算法要求。")
                ]
            }),
            
            new Paragraph({
                spacing: { before: 100 },
                children: [
                    createBold("【缺点】："),
                    createText('文本被传统新闻通稿深度绑架。在吃瓜、造梗的快节奏情绪场中，强塞"系统践行传播范式"等学术/业务黑话，势必导致极高的推流划过率。')
                ]
            }),
            
            new Paragraph({
                spacing: { before: 100 },
                children: [
                    createBold("【优化意见】："),
                    createText('彻底抛弃理论阐述。提纯"青年主播天团"的IP人设，将文案压缩至140字内，用强冲突的网感语言在末尾抛出诱导性提问，蓄水评论区。')
                ]
            }),
            
            // 抖音
            new Paragraph({
                heading: HeadingLevel.HEADING_2,
                children: [new TextRun("3. 抖音与视频号：冗余文案干扰视觉算法")]
            }),
            
            new Paragraph({
                spacing: { before: 150 },
                children: [
                    createBold("抽取样本："),
                    createText('"浙报集团希望通过该产品系统性培育一批有思想锋芒...为主流媒体系统性变革提供了有益的尝试。"')
                ]
            }),
            
            new Paragraph({
                spacing: { before: 100 },
                children: [
                    createBold("【优点】："),
                    createText('视频号部分切片挂载了特有语气词（"这回不玩虚的"）及中英双语Hashtag，初步具备国际传播占位意识。')
                ]
            }),
            
            new Paragraph({
                spacing: { before: 100 },
                children: [
                    createBold("【缺点】："),
                    createText('严重违背短视频生态"重视觉、轻文本"的核心逻辑。长篇大论不仅在UI界面必然被折叠，更会严重干扰算法模型对视频画面的特征抓取，属于典型的负向拉拽。')
                ]
            }),
            
            new Paragraph({
                spacing: { before: 100 },
                children: [
                    createBold("【优化意见】："),
                    createText("执行极简文案法则。抖音文本严格控制在20-40字以内，将外籍、00后、硬核对线等高转化爆点强行前置于黄金三秒。")
                ]
            }),
            
            // 头条
            new Paragraph({
                heading: HeadingLevel.HEADING_2,
                children: [new TextRun("4. 今日头条：通报体无法击穿推荐阈值")]
            }),
            
            new Paragraph({
                spacing: { before: 150 },
                children: [
                    createBold("抽取样本："),
                    createText('"浙报集团年度重磅产品\'潮声·青年说\'1日后将闪亮登场"')
                ]
            }),
            
            new Paragraph({
                spacing: { before: 100 },
                children: [
                    createBold("【优点】："),
                    createText("无明显适配该平台的优点，仅起到了基础的信息占位作用。")
                ]
            }),
            
            new Paragraph({
                spacing: { before: 100 },
                children: [
                    createBold("【缺点】："),
                    createText('纯机器推荐算法驱动的头条引擎，极度嗜好"高信息密度"与"悬念情绪"。此类干瘪的内部通报完全无法触发其基础的推荐分发阈值。')
                ]
            }),
            
            new Paragraph({
                spacing: { before: 100 },
                children: [
                    createBold("【优化意见】："),
                    createText('必须重构为"三段式悬念标题"（背景设定+核心冲突+结果预告），以拉升点击转化率。')
                ]
            }),
            
            // 分页
            new Paragraph({ children: [new PageBreak()] }),
            
            // 第三部分
            new Paragraph({
                heading: HeadingLevel.HEADING_1,
                children: [new TextRun("三、整体评估与下阶段战略建议")]
            }),
            
            new Paragraph({
                spacing: { before: 200, after: 200 },
                children: [createText('从本次数据与文本特征来看，历史报告中反复提及的"一稿多投、浓厚通稿味"问题依然严峻，物料中央厨房的拆解分发机制仍未真实落地。虽然集团展现了短时间内64篇齐发的强悍矩阵执行力，但缺乏精细化运营导致的流量损耗极其惊人。')]
            }),
            
            new Paragraph({
                spacing: { before: 200 },
                children: [createText("针对正片发布与切片传播期，业务侧必须立即切入以下Action动作：")]
            }),
            
            new Paragraph({
                spacing: { before: 200 },
                children: [createBold('1. 彻底熔断"通稿通发"机制')]
            }),
            new Paragraph({
                spacing: { before: 100 },
                children: [createText('倒逼"物料中央厨房+分平台定制"跑通。单期播客必须裂变为多形态：公众号主攻"深度解析"、抖音强推"情绪金句切片"、微博专攻"话题争议引流"。')]
            }),
            
            new Paragraph({
                spacing: { before: 200 },
                children: [createBold("2. 升维个人IP资产")]
            }),
            new Paragraph({
                spacing: { before: 100 },
                children: [createText('理论传播的底层逻辑在C端必须软化。在"潮声"的理论底色之上，必须重仓押注张萍、李灿、戴佳轶、苏黛4位主播的"人设标签"，用粉"人"的逻辑去带听"课"的留存。')]
            }),
            
            new Paragraph({
                spacing: { before: 200 },
                children: [createBold("3. 闭环数据漏斗归因")]
            }),
            new Paragraph({
                spacing: { before: 100 },
                children: [createText('推动底层数据补全。在下期正片链路中，重点建立跨端追踪体系，量化评估"抖音前端高曝光"向"公众号/客户端深阅读"的转化漏斗损耗，为后续买量与推流提供真实ROI依据。')]
            }),
            
            // 底部信息
            new Paragraph({ spacing: { before: 600 } }),
            new Paragraph({
                alignment: AlignmentType.CENTER,
                children: [new TextRun({ text: "— 简报完 —", size: 20, color: "95A5A6" })]
            }),
            new Paragraph({
                alignment: AlignmentType.CENTER,
                spacing: { before: 100 },
                children: [new TextRun({ text: "DATA EMPOWERMENT · 省级融媒体中心数据中台", size: 18, color: "BDC3C7" })]
            })
        ]
    }]
});

// 生成文档
Packer.toBuffer(doc).then(buffer => {
    fs.writeFileSync('/sessions/69fb62913bdc1557ad8b2704/workspace/潮声青年说_预热期数据简报.docx', buffer);
    console.log('Word文档已生成！');
}).catch(err => {
    console.error('生成失败:', err);
});
