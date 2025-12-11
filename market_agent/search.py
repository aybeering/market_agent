"""
Search - 事件期货可行性分析的主入口
"""

import os
import time
import uuid
import logging
from typing import Optional, Callable, Awaitable, Any
from pathlib import Path

# 自动加载 .env 文件
from dotenv import load_dotenv

# 从 market-agent 根目录加载 .env
_package_root = Path(__file__).parent.parent  # market_agent 的父目录即 market-agent
_env_path = _package_root / ".env"

if _env_path.exists():
    load_dotenv(_env_path)
else:
    # 备选：尝试默认加载
    load_dotenv()

from .result import SearchResult

logger = logging.getLogger(__name__)

# 进度回调类型定义
ProgressCallback = Callable[[str, str, str], Awaitable[None]]
# 参数: (node_name, status, message)


class Search:
    """
    事件期货可行性分析工具
    
    使用方法:
        result = await Search.go("比特币2025年突破15万美元")
        
        if result.success:
            print(result.report)
        else:
            print(result.error)
    """
    
    # 工作流节点名称映射（用于进度回调）
    NODE_NAMES = {
        "grounding": "事件背景分析",
        "quantifiability_analyzer": "可量化性分析",
        "oracle_analyzer": "预言机分析",
        "market_demand_analyzer": "市场需求分析",
        "compliance_risk_analyzer": "合规风险分析",
        "collector": "数据收集",
        "curator": "数据筛选",
        "enricher": "内容增强",
        "briefing": "简报生成",
        "editor": "报告编译",
    }
    
    @staticmethod
    async def go(
        topic: str,
        event_category: Optional[str] = None,
        target_date: Optional[str] = None,
        job_id: Optional[str] = None,
        on_progress: Optional[ProgressCallback] = None,
    ) -> SearchResult:
        """
        执行事件期货可行性分析
        
        Args:
            topic: 事件话题（必填）
                例如: "比特币2025年突破15万美元"
            event_category: 事件类别（可选，自动推断）
                例如: "加密货币", "政治", "体育", "科技"
            target_date: 预期结算日期（可选）
                例如: "2025-12-31"
            job_id: 任务ID（可选，自动生成UUID）
            on_progress: 进度回调函数（可选）
                签名: async def callback(node: str, status: str, message: str)
        
        Returns:
            SearchResult: 结构化的分析结果
            
        Example:
            # 基本用法
            result = await Search.go("2025年美联储降息至少3次")
            
            # 带进度回调
            async def show_progress(node, status, msg):
                print(f"[{node}] {msg}")
            
            result = await Search.go(
                topic="SpaceX星舰成功登陆火星",
                event_category="航天",
                target_date="2026-12-31",
                on_progress=show_progress
            )
        """
        # 参数验证
        if not topic or not topic.strip():
            return SearchResult.from_error(
                error="topic 参数不能为空",
                error_details={"param": "topic", "value": topic}
            )
        
        topic = topic.strip()
        
        # 生成 job_id
        if job_id is None:
            job_id = f"search-{uuid.uuid4().hex[:12]}"
        
        # 记录开始时间
        start_time = time.time()
        
        try:
            # 延迟导入，避免循环依赖
            from workflow.backend.graph import Graph
            
            # 通知开始
            if on_progress:
                await on_progress("system", "started", f"开始分析: {topic}")
            
            # 创建工作流
            graph = Graph(
                topic=topic,
                event_category=event_category,
                target_date=target_date or "",
                job_id=job_id
            )
            
            thread = {"configurable": {"thread_id": job_id}}
            
            # 跟踪已完成的节点
            completed_nodes = set()
            final_state = None
            
            # 执行工作流
            async for state in graph.run(thread):
                # 检测当前完成的节点
                for node_key in state.keys():
                    if node_key not in completed_nodes and node_key in Search.NODE_NAMES:
                        completed_nodes.add(node_key)
                        
                        # 触发进度回调
                        if on_progress:
                            node_name = Search.NODE_NAMES.get(node_key, node_key)
                            await on_progress(
                                node_key, 
                                "completed", 
                                f"✓ {node_name} 完成"
                            )
                
                # 检查是否生成了最终报告
                if "editor" in state and isinstance(state.get("editor"), dict):
                    if state["editor"].get("report"):
                        final_state = state
                        break
                
                # 备份最新状态
                final_state = state
            
            elapsed_time = time.time() - start_time
            
            # 构建结果
            if final_state is None:
                return SearchResult.from_error(
                    error="工作流未返回任何状态",
                    topic=topic,
                    job_id=job_id
                )
            
            result = SearchResult.from_state(final_state, job_id, elapsed_time, topic=topic)
            
            # 通知完成
            if on_progress:
                if result.success:
                    await on_progress(
                        "system", 
                        "completed", 
                        f"✅ 分析完成，耗时 {elapsed_time:.1f} 秒"
                    )
                else:
                    await on_progress(
                        "system", 
                        "failed", 
                        f"❌ 分析失败: {result.error}"
                    )
            
            return result
            
        except ImportError as e:
            elapsed_time = time.time() - start_time
            error_msg = f"无法导入工作流模块: {str(e)}"
            logger.error(error_msg)
            
            if on_progress:
                await on_progress("system", "error", error_msg)
            
            return SearchResult.from_error(
                error=error_msg,
                topic=topic,
                job_id=job_id,
                error_details={"exception": str(e), "type": "ImportError"}
            )
            
        except Exception as e:
            elapsed_time = time.time() - start_time
            error_msg = f"工作流执行失败: {str(e)}"
            logger.exception(error_msg)
            
            if on_progress:
                await on_progress("system", "error", error_msg)
            
            return SearchResult.from_error(
                error=error_msg,
                topic=topic,
                job_id=job_id,
                error_details={
                    "exception": str(e),
                    "type": type(e).__name__,
                    "elapsed_time": elapsed_time
                }
            )
    
    @staticmethod
    def go_sync(
        topic: str,
        event_category: Optional[str] = None,
        target_date: Optional[str] = None,
        job_id: Optional[str] = None,
    ) -> SearchResult:
        """
        同步版本的 go 方法（不支持进度回调）
        
        注意: 此方法会阻塞当前线程直到完成
        
        Args:
            topic: 事件话题（必填）
            event_category: 事件类别（可选）
            target_date: 预期结算日期（可选）
            job_id: 任务ID（可选）
        
        Returns:
            SearchResult: 结构化的分析结果
        """
        import asyncio
        
        return asyncio.run(Search.go(
            topic=topic,
            event_category=event_category,
            target_date=target_date,
            job_id=job_id,
            on_progress=None
        ))
