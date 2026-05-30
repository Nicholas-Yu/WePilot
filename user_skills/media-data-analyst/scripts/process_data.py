"""
媒体数据分析师 - 数据处理脚本
用途：从 xlsx 中提取并统计数据，输出 JSON 供后续报告生成使用
输入：xlsx 文件路径
输出：JSON 统计结果
"""

import pandas as pd
import numpy as np
import json
import sys
import os

def validate_data(xls_path):
    """数据校验"""
    xls = pd.ExcelFile(xls_path)
    warnings = []
    
    # Sheet 存在性检查
    expected_sheets = ['作品数据', '微博话题数据']
    actual_sheets = xls.sheet_names
    for s in expected_sheets:
        if s not in actual_sheets:
            # 尝试模糊匹配
            matched = [name for name in actual_sheets if '作品' in name or 'work' in name.lower()]
            if not matched and '话题' in s:
                matched = [name for name in actual_sheets if '话题' in name or 'topic' in name.lower()]
            warnings.append(f"未找到 Sheet '{s}'，可用 Sheet: {actual_sheets}")
    
    return xls, warnings


def process_works_data(df):
    """处理作品数据，按平台维度统计"""
    # 清洗数值列
    numeric_cols = ['预估播放数/阅读数', '获赞数/推荐数', '评论数', '分享数', 
                    '收藏数/喜欢数', '互动量', '互动率']
    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
    
    # 按平台聚合
    platform_stats = []
    for platform in df['平台'].unique():
        pdf = df[df['平台'] == platform]
        count = len(pdf)
        reads = int(pdf['预估播放数/阅读数'].sum()) if '预估播放数/阅读数' in pdf.columns else 0
        likes = int(pdf['获赞数/推荐数'].sum()) if '获赞数/推荐数' in pdf.columns else 0
        comments = int(pdf['评论数'].sum()) if '评论数' in pdf.columns else 0
        shares = int(pdf['分享数'].sum()) if '分享数' in pdf.columns else 0
        favs = int(pdf['收藏数/喜欢数'].sum()) if '收藏数/喜欢数' in pdf.columns else 0
        interacts = int(pdf['互动量'].sum()) if '互动量' in pdf.columns else 0
        avg_rate = pdf['互动率'].mean() if '互动率' in pdf.columns else 0
        
        platform_stats.append({
            'platform': platform,
            'count': count,
            'reads': reads,
            'likes': likes,
            'comments': comments,
            'shares': shares,
            'favs': favs,
            'interacts': interacts,
            'rate': f"{avg_rate*100:.2f}%" if avg_rate > 0 else 'N/A'
        })
    
    # 识别三大角色
    has_reads = [s for s in platform_stats if s['reads'] > 0]
    breakout = max(has_reads, key=lambda x: x['reads']) if has_reads else None
    pivot = max(platform_stats, key=lambda x: x['shares']) if platform_stats else None
    deep = max([s for s in platform_stats if s != breakout], key=lambda x: x['favs']) if len(platform_stats) > 1 else None
    
    return {
        'platform_stats': platform_stats,
        'total_posts': len(df),
        'breakout_platform': breakout,
        'pivot_platform': pivot,
        'deep_platform': deep,
        'needs_exemption': any(s['reads'] == 0 for s in platform_stats if s['platform'] in ['微博', '视频号'])
    }


def process_topic_data(df):
    """处理微博话题数据，去重分析"""
    # 清洗
    if '话题阅读量' in df.columns:
        df['话题阅读量'] = pd.to_numeric(df['话题阅读量'], errors='coerce').fillna(0)
    if '排名' in df.columns:
        df['排名'] = pd.to_numeric(df['排名'], errors='coerce')
    
    # 按话题去重
    topic_analysis = []
    for topic in df['相关话题'].unique():
        tdf = df[df['相关话题'] == topic]
        max_reads = int(tdf['话题阅读量'].max()) if '话题阅读量' in tdf.columns else 0
        accounts = tdf['发布账号'].unique().tolist()
        host = tdf['话题主持人'].iloc[0] if '话题主持人' in tdf.columns and len(tdf) > 0 else ''
        
        # 热搜统计
        hot_channels = tdf['热搜渠道'].dropna().unique().tolist()
        ranks = tdf['排名'].dropna().tolist()
        valid_ranks = [int(r) for r in ranks if pd.notna(r) and r != '\\N']
        
        topic_analysis.append({
            'topic': topic,
            'max_reads': max_reads,
            'account_count': len(accounts),
            'accounts': accounts[:5],  # 取前5个
            'host': host,
            'hot_channel_count': len(hot_channels),
            'hot_channels': hot_channels[:5],
            'best_rank': min(valid_ranks) if valid_ranks else None,
            'sample_content': tdf['发布内容'].iloc[0][:100] if len(tdf) > 0 and '发布内容' in tdf.columns else ''
        })
    
    # 按阅读量排序
    topic_analysis.sort(key=lambda x: x['max_reads'], reverse=True)
    
    return topic_analysis


def extract_content_samples(df):
    """提取各平台文案样本"""
    samples = {}
    target_platforms = ['公众号', '微博', '抖音', '今日头条', '视频号']
    
    for platform in target_platforms:
        pdf = df[df['平台'] == platform]
        if len(pdf) > 0:
            row = pdf.iloc[0]
            title = str(row['标题'])[:80] if pd.notna(row.get('标题')) else ''
            samples[platform] = {
                'title': title,
                'account': str(row['昵称']) if pd.notna(row.get('昵称')) else ''
            }
    
    return samples


def main():
    if len(sys.argv) < 2:
        print("用法: python process_data.py <xlsx文件路径> [输出JSON路径]")
        sys.exit(1)
    
    xlsx_path = sys.argv[1]
    output_path = sys.argv[2] if len(sys.argv) > 2 else 'analysis_result.json'
    
    # 校验
    xls, warnings = validate_data(xlsx_path)
    for w in warnings:
        print(f"[WARNING] {w}")
    
    # 读取数据
    works_sheet = [s for s in xls.sheet_names if '作品' in s][0] if any('作品' in s for s in xls.sheet_names) else xls.sheet_names[0]
    topic_sheet = [s for s in xls.sheet_names if '话题' in s][0] if any('话题' in s for s in xls.sheet_names) else xls.sheet_names[1] if len(xls.sheet_names) > 1 else None
    
    works_df = pd.read_excel(xls, works_sheet)
    topic_df = pd.read_excel(xls, topic_sheet) if topic_sheet else pd.DataFrame()
    
    # 处理
    works_result = process_works_data(works_df)
    topic_result = process_topic_data(topic_df) if not topic_df.empty else []
    content_samples = extract_content_samples(works_df)
    
    # 汇总
    result = {
        'works': works_result,
        'topics': topic_result,
        'samples': content_samples,
        'warnings': warnings
    }
    
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    
    print(f"分析完成！结果已保存到 {output_path}")
    print(f"平台数: {len(works_result['platform_stats'])}, 总物料: {works_result['total_posts']}")
    print(f"话题数: {len(topic_result)}")


if __name__ == '__main__':
    main()
