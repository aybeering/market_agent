#!/usr/bin/env python3
"""
综合测试脚本：测试 Token 消耗 / 生成稳定性 / 话题覆盖能力
"""

import asyncio
import json
import os
import re
import time
from datetime import datetime
from typing import Dict, List, Any
from dotenv import load_dotenv

load_dotenv()

from workflow.backend.graph import Graph

# 15个多样化话题，覆盖不同类别
TEST_TOPICS = [
    # 经济/金融类
    {'topic': '2025年美联储降息至少3次', 'category': '经济/货币政策', 'date': '2025-12-31'},
    {'topic': '比特币2025年突破15万美元', 'category': '加密货币', 'date': '2025-12-31'},
    {'topic': '特斯拉股价2025年翻倍', 'category': '股票', 'date': '2025-12-31'},
    
    # 政治/地缘类
    {'topic': '2025年俄乌战争停火协议签署', 'category': '地缘政治', 'date': '2025-12-31'},
    {'topic': '2025年中美关税全面取消', 'category': '国际贸易', 'date': '2025-12-31'},
    
    # 科技类
    {'topic': 'OpenAI发布GPT-5', 'category': '人工智能', 'date': '2025-12-31'},
    {'topic': '苹果2025年发布AR眼镜', 'category': '消费电子', 'date': '2025-12-31'},
    {'topic': 'SpaceX星舰成功进入火星轨道', 'category': '航天', 'date': '2026-12-31'},
    
    # 体育类
    {'topic': '2026年世界杯阿根廷卫冕成功', 'category': '体育/足球', 'date': '2026-07-19'},
    {'topic': '2028洛杉矶奥运会中国金牌第一', 'category': '体育/奥运', 'date': '2028-08-11'},
    
    # 气候/环境类
    {'topic': '2025年全球平均气温创历史新高', 'category': '气候', 'date': '2025-12-31'},
    
    # 公共卫生类
    {'topic': 'WHO宣布新冠大流行正式结束', 'category': '公共卫生', 'date': '2025-12-31'},
    
    # 商业/企业类
    {'topic': '英伟达市值2025年超过苹果', 'category': '科技股', 'date': '2025-12-31'},
    
    # 自然灾害类（高不确定性）
    {'topic': '2025年日本发生8级以上地震', 'category': '自然灾害', 'date': '2025-12-31'},
    
    # 娱乐类
    {'topic': '2025年奥斯卡最佳影片由AI生成电影获得', 'category': '娱乐', 'date': '2025-03-02'},
]


def estimate_tokens(text: str) -> int:
    """粗略估算 token 数量（中文约 1.5 字符/token，英文约 4 字符/token）"""
    chinese_chars = len(re.findall(r'[\u4e00-\u9fff]', text))
    other_chars = len(text) - chinese_chars
    return int(chinese_chars / 1.5 + other_chars / 4)


def extract_scores(report: str) -> Dict[str, Any]:
    """从报告中提取评分"""
    scores = {
        'quantifiability': None,
        'oracle': None,
        'market_demand': None,
        'compliance_risk': None,
        'overall': None,
        'recommendation': None
    }
    
    # 匹配评分模式
    patterns = {
        'quantifiability': r'可量化性[^0-9]*?(\d+)/10|维度评分[：:]\s*(\d+)/10.*?可量化',
        'oracle': r'预言机[^0-9]*?(\d+)/10|结算机制评分[：:]\s*(\d+)/10',
        'market_demand': r'市场需求[^0-9]*?(\d+)/10|需求评分[：:]\s*(\d+)/10',
        'compliance_risk': r'合规[^0-9]*?(\d+)/10|风险评分[：:]\s*(\d+)/10',
        'overall': r'总评分[：:]\s*(\d+\.?\d*)/10|综合[得评]分[：:]\s*(\d+\.?\d*)/10'
    }
    
    for key, pattern in patterns.items():
        match = re.search(pattern, report, re.IGNORECASE)
        if match:
            for g in match.groups():
                if g:
                    scores[key] = float(g)
                    break
    
    # 提取推荐决策
    if '推荐上线' in report:
        scores['recommendation'] = '推荐上线'
    elif '谨慎上线' in report:
        scores['recommendation'] = '谨慎上线'
    elif '不推荐' in report or '暂不推荐' in report:
        scores['recommendation'] = '不推荐上线'
    
    return scores


def check_report_structure(report: str) -> Dict[str, bool]:
    """检查报告结构完整性"""
    required_sections = {
        '事件概述': bool(re.search(r'##.*事件概述|## 事件概述', report)),
        '可量化性评估': bool(re.search(r'##.*可量化性|## 可量化性评估', report)),
        '预言机与结算': bool(re.search(r'##.*预言机|## 预言机', report)),
        '市场需求分析': bool(re.search(r'##.*市场需求|## 市场需求', report)),
        '合规与风险': bool(re.search(r'##.*合规|## 合规', report)),
        '综合结论': bool(re.search(r'##.*综合结论|## 综合结论|##.*结论', report)),
    }
    return required_sections


async def run_single_test(topic_info: Dict, index: int) -> Dict[str, Any]:
    """运行单个话题测试"""
    result = {
        'index': index + 1,
        'topic': topic_info['topic'],
        'category': topic_info['category'],
        'status': 'pending',
        'time_seconds': 0,
        'report_length': 0,
        'estimated_tokens': 0,
        'scores': {},
        'structure': {},
        'structure_complete': False,
        'error': None
    }
    
    start_time = time.time()
    
    try:
        print(f"\n[{index+1}/{len(TEST_TOPICS)}] 🔄 测试中: {topic_info['topic']}")
        
        g = Graph(
            topic=topic_info['topic'],
            event_category=topic_info['category'],
            target_date=topic_info['date'],
            job_id=f'comprehensive-test-{index+1}'
        )
        
        thread = {'configurable': {'thread_id': f'test-thread-{index+1}'}}
        final_report = None
        
        async for state in g.run(thread):
            if 'editor' in state and state['editor'].get('report'):
                final_report = state['editor']['report']
        
        elapsed = time.time() - start_time
        result['time_seconds'] = round(elapsed, 1)
        
        if final_report:
            result['status'] = 'success'
            result['report_length'] = len(final_report)
            result['estimated_tokens'] = estimate_tokens(final_report)
            result['scores'] = extract_scores(final_report)
            result['structure'] = check_report_structure(final_report)
            result['structure_complete'] = all(result['structure'].values())
            
            # 保存报告
            safe_name = topic_info['topic'].replace('/', '_').replace(' ', '_')[:30]
            filename = f'reports/comprehensive_{index+1:02d}_{safe_name}.md'
            os.makedirs('reports', exist_ok=True)
            with open(filename, 'w', encoding='utf-8') as f:
                f.write(final_report)
            
            print(f"    ✅ 成功 | {elapsed:.1f}s | {result['report_length']}字 | ~{result['estimated_tokens']}tokens")
            print(f"       评分: 量化{result['scores'].get('quantifiability', '?')}/预言机{result['scores'].get('oracle', '?')}/需求{result['scores'].get('market_demand', '?')}/合规{result['scores'].get('compliance_risk', '?')}")
        else:
            result['status'] = 'failed'
            result['error'] = 'No report generated'
            print(f"    ❌ 失败: 无报告生成")
            
    except Exception as e:
        elapsed = time.time() - start_time
        result['status'] = 'error'
        result['time_seconds'] = round(elapsed, 1)
        result['error'] = str(e)[:200]
        print(f"    ❌ 错误: {str(e)[:100]}")
    
    return result


async def main():
    print("=" * 70)
    print("🧪 事件期货可行性报告 - 综合测试")
    print(f"📅 测试时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"📊 测试话题数: {len(TEST_TOPICS)}")
    print("=" * 70)
    
    all_results = []
    total_start = time.time()
    
    # 顺序执行测试
    for i, topic in enumerate(TEST_TOPICS):
        result = await run_single_test(topic, i)
        all_results.append(result)
    
    total_time = time.time() - total_start
    
    # 汇总统计
    print("\n" + "=" * 70)
    print("📈 测试结果汇总")
    print("=" * 70)
    
    success_results = [r for r in all_results if r['status'] == 'success']
    failed_results = [r for r in all_results if r['status'] != 'success']
    
    # 1. 基础统计
    print(f"\n### 1. 基础统计")
    print(f"   成功率: {len(success_results)}/{len(all_results)} ({100*len(success_results)/len(all_results):.1f}%)")
    print(f"   总耗时: {total_time:.1f}秒")
    print(f"   平均耗时: {total_time/len(all_results):.1f}秒/话题")
    
    if success_results:
        avg_length = sum(r['report_length'] for r in success_results) / len(success_results)
        avg_tokens = sum(r['estimated_tokens'] for r in success_results) / len(success_results)
        print(f"   平均报告长度: {avg_length:.0f}字符")
        print(f"   平均Token消耗: ~{avg_tokens:.0f} tokens/报告")
    
    # 2. Token消耗分析
    print(f"\n### 2. Token消耗分析")
    if success_results:
        tokens = [r['estimated_tokens'] for r in success_results]
        print(f"   最小: ~{min(tokens)} tokens")
        print(f"   最大: ~{max(tokens)} tokens")
        print(f"   平均: ~{sum(tokens)/len(tokens):.0f} tokens")
        print(f"   总计: ~{sum(tokens)} tokens (仅输出)")
        # 估算输入token（假设输入是输出的2倍）
        estimated_input = sum(tokens) * 2
        print(f"   估算输入: ~{estimated_input} tokens")
        print(f"   估算总消耗: ~{sum(tokens) + estimated_input} tokens")
    
    # 3. 生成稳定性分析
    print(f"\n### 3. 生成稳定性分析")
    structure_complete_count = sum(1 for r in success_results if r.get('structure_complete', False))
    print(f"   结构完整率: {structure_complete_count}/{len(success_results)} ({100*structure_complete_count/max(1,len(success_results)):.1f}%)")
    
    # 检查各部分完成情况
    section_stats = {}
    for r in success_results:
        for section, present in r.get('structure', {}).items():
            if section not in section_stats:
                section_stats[section] = {'present': 0, 'missing': 0}
            if present:
                section_stats[section]['present'] += 1
            else:
                section_stats[section]['missing'] += 1
    
    print("   各部分生成率:")
    for section, stats in section_stats.items():
        rate = 100 * stats['present'] / (stats['present'] + stats['missing'])
        status = "✅" if rate == 100 else "⚠️" if rate >= 80 else "❌"
        print(f"     {status} {section}: {rate:.0f}%")
    
    # 4. 评分分布
    print(f"\n### 4. 评分分布")
    score_fields = ['quantifiability', 'oracle', 'market_demand', 'compliance_risk', 'overall']
    for field in score_fields:
        scores = [r['scores'].get(field) for r in success_results if r['scores'].get(field) is not None]
        if scores:
            avg = sum(scores) / len(scores)
            field_cn = {'quantifiability': '可量化性', 'oracle': '预言机', 'market_demand': '市场需求', 
                       'compliance_risk': '合规风险', 'overall': '综合评分'}
            print(f"   {field_cn.get(field, field)}: 平均{avg:.1f}/10 (范围{min(scores)}-{max(scores)}, n={len(scores)})")
    
    # 5. 推荐分布
    print(f"\n### 5. 推荐决策分布")
    recommendations = [r['scores'].get('recommendation') for r in success_results]
    rec_counts = {}
    for rec in recommendations:
        if rec:
            rec_counts[rec] = rec_counts.get(rec, 0) + 1
    for rec, count in sorted(rec_counts.items(), key=lambda x: -x[1]):
        print(f"   {rec}: {count}个 ({100*count/len(success_results):.1f}%)")
    
    # 6. 话题覆盖能力
    print(f"\n### 6. 话题覆盖能力")
    category_results = {}
    for r in all_results:
        cat = r['category']
        if cat not in category_results:
            category_results[cat] = {'success': 0, 'total': 0, 'topics': []}
        category_results[cat]['total'] += 1
        category_results[cat]['topics'].append(r['topic'][:20])
        if r['status'] == 'success':
            category_results[cat]['success'] += 1
    
    print("   按类别成功率:")
    for cat, stats in sorted(category_results.items()):
        rate = 100 * stats['success'] / stats['total']
        status = "✅" if rate == 100 else "❌"
        print(f"     {status} {cat}: {stats['success']}/{stats['total']}")
    
    # 7. 失败案例
    if failed_results:
        print(f"\n### 7. 失败案例")
        for r in failed_results:
            print(f"   ❌ {r['topic']}: {r.get('error', 'Unknown error')[:80]}")
    
    # 8. 详细结果表
    print(f"\n### 8. 详细结果")
    print(f"{'#':<3} {'话题':<25} {'类别':<12} {'状态':<6} {'耗时':<8} {'字数':<8} {'Tokens':<8} {'综合分':<6}")
    print("-" * 90)
    for r in all_results:
        status = "✅" if r['status'] == 'success' else "❌"
        overall = r['scores'].get('overall', '-') if r['status'] == 'success' else '-'
        print(f"{r['index']:<3} {r['topic'][:24]:<25} {r['category'][:11]:<12} {status:<6} {r['time_seconds']:<8} {r['report_length']:<8} {r['estimated_tokens']:<8} {overall}")
    
    # 保存JSON结果
    with open('reports/comprehensive_test_results.json', 'w', encoding='utf-8') as f:
        json.dump({
            'test_time': datetime.now().isoformat(),
            'total_topics': len(TEST_TOPICS),
            'success_count': len(success_results),
            'total_time_seconds': round(total_time, 1),
            'avg_time_per_topic': round(total_time / len(all_results), 1),
            'avg_tokens': round(sum(r['estimated_tokens'] for r in success_results) / max(1, len(success_results))),
            'results': all_results
        }, f, ensure_ascii=False, indent=2)
    
    print(f"\n📄 详细结果已保存到 reports/comprehensive_test_results.json")
    print("=" * 70)


if __name__ == '__main__':
    asyncio.run(main())
