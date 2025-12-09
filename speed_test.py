#!/usr/bin/env python3
"""速度测试脚本"""

import asyncio
import time
from dotenv import load_dotenv
load_dotenv()
from workflow.backend.graph import Graph

async def test():
    start = time.time()
    g = Graph(
        topic='WHO宣布新冠疫情结束', 
        event_category='公共卫生', 
        target_date='2025-12-31', 
        job_id='speed-test-2'
    )
    thread = {'configurable': {'thread_id': 'speed-2'}}
    async for state in g.run(thread):
        if 'editor' in state and state['editor'].get('report'):
            elapsed = time.time() - start
            print(f'✅ 完成: {len(state["editor"]["report"])} 字符')
            print(f'⏱️ 耗时: {elapsed:.1f} 秒')
            break

asyncio.run(test())
