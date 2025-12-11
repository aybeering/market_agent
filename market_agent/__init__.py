"""
Market Agent - 事件期货可行性分析工具

使用方法:
    from market_agent import Search
    
    # 异步调用
    result = await Search.go("比特币2025年突破15万美元")
    
    # 带进度回调
    async def on_progress(node, status, message):
        print(f"[{node}] {status}: {message}")
    
    result = await Search.go(
        topic="比特币2025年突破15万美元",
        event_category="加密货币",
        target_date="2025-12-31",
        on_progress=on_progress
    )
    
    # 访问结果
    if result.success:
        print(result.report)
        print(f"可行性评分: {result.feasibility_score}")
    else:
        print(f"错误: {result.error}")
"""

from .search import Search
from .result import SearchResult

__all__ = ["Search", "SearchResult"]
__version__ = "1.0.0"
