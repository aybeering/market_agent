#!/usr/bin/env python3
"""批量测试事件期货可行性报告生成"""

import asyncio
import os
from datetime import datetime
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

from workflow.backend.graph import Graph

# 3个快速测试话题
TOPICS = [
    {'topic': '比特币2025年突破15万美元', 'category': '加密货币', 'date': '2025-12-31'},
    {'topic': '2026年世界杯阿根廷夺冠', 'category': '体育', 'date': '2026-07-19'},
    {'topic': 'WHO宣布新冠疫情彻底结束', 'category': '公共卫生', 'date': '2025-12-31'},
]


async def run_single_topic(topic_info, index):
    """运行单个话题分析"""
    try:
        print(f'\n[{index+1}/15] 🔄 分析中: {topic_info["topic"]}')
        
        g = Graph(
            topic=topic_info['topic'],
            event_category=topic_info['category'],
            target_date=topic_info['date'],
            job_id=f'batch-{index+1}'
        )
        
        thread = {'configurable': {'thread_id': f'batch-thread-{index+1}'}}
        final_report = None
        
        async for state in g.run(thread):
            if 'editor' in state and state['editor'].get('report'):
                final_report = state['editor']['report']
        
        if final_report:
            # 保存到单独文件
            safe_name = topic_info['topic'].replace('/', '_').replace(' ', '_')[:30]
            filename = f'reports/report_{index+1:02d}_{safe_name}.md'
            os.makedirs('reports', exist_ok=True)
            with open(filename, 'w', encoding='utf-8') as f:
                f.write(final_report)
            print(f'    ✅ 完成: {len(final_report)} 字符')
            return {'topic': topic_info['topic'], 'status': 'success', 'length': len(final_report), 'file': filename}
        else:
            print(f'    ❌ 失败: 无报告生成')
            return {'topic': topic_info['topic'], 'status': 'failed', 'error': 'No report generated'}
    except Exception as e:
        print(f'    ❌ 错误: {str(e)[:100]}')
        return {'topic': topic_info['topic'], 'status': 'error', 'error': str(e)}


async def batch_test():
    print('='*60)
    print('🚀 事件期货可行性报告批量测试')
    print(f'📊 共 {len(TOPICS)} 个话题')
    print('='*60)
    
    start_time = datetime.now()
    results = []
    
    # 顺序执行，避免 API 限流
    for i, topic in enumerate(TOPICS):
        result = await run_single_topic(topic, i)
        results.append(result)
    
    end_time = datetime.now()
    duration = (end_time - start_time).total_seconds()
    
    # 统计结果
    success = sum(1 for r in results if r['status'] == 'success')
    failed = len(results) - success
    
    print('\n' + '='*60)
    print('📈 批量测试结果汇总')
    print('='*60)
    print(f'✅ 成功: {success}/{len(TOPICS)}')
    print(f'❌ 失败: {failed}/{len(TOPICS)}')
    print(f'⏱️ 总耗时: {duration:.1f} 秒')
    print(f'⏱️ 平均每个: {duration/len(TOPICS):.1f} 秒')
    
    # 生成汇总报告
    summary = f'''# 事件期货可行性报告批量测试汇总

## 测试概况
- **测试时间**: {start_time.strftime('%Y-%m-%d %H:%M:%S')}
- **话题数量**: {len(TOPICS)}
- **成功率**: {success}/{len(TOPICS)} ({100*success/len(TOPICS):.1f}%)
- **总耗时**: {duration:.1f} 秒
- **平均耗时**: {duration/len(TOPICS):.1f} 秒/话题

## 测试结果详情

| # | 话题 | 类别 | 状态 | 报告长度 |
|---|------|------|------|----------|
'''
    for i, (topic, result) in enumerate(zip(TOPICS, results)):
        status = '✅' if result['status'] == 'success' else '❌'
        length = result.get('length', '-')
        summary += f"| {i+1} | {topic['topic'][:25]}... | {topic['category']} | {status} | {length} |\n"
    
    os.makedirs('reports', exist_ok=True)
    with open('reports/batch_summary.md', 'w', encoding='utf-8') as f:
        f.write(summary)
    
    print(f'\n📄 汇总报告已保存到 reports/batch_summary.md')


if __name__ == '__main__':
    asyncio.run(batch_test())
