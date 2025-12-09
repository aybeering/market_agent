import logging
import os

from langchain_core.messages import AIMessage
from tavily import AsyncTavilyClient

from ..classes import InputState, ResearchState
from ..classes.state import job_status

logger = logging.getLogger(__name__)

class GroundingNode:
    """解析事件话题，收集事件背景信息。"""
    
    def __init__(self) -> None:
        self.tavily_client = AsyncTavilyClient(api_key=os.getenv("TAVILY_API_KEY"))

    async def initial_search(self, state: InputState):
        """初始搜索事件背景信息并生成事件"""
        topic = state.get('topic', 'Unknown Topic')
        job_id = state.get('job_id')
        msg = f"🎯 开始分析事件: {topic}...\n"
        
        # Emit initialization event
        event = {
            "type": "research_init",
            "topic": topic,
            "message": f"开始分析事件: {topic}",
            "step": "初始化"
        }
        
        if job_id:
            try:
                if job_id in job_status:
                    job_status[job_id]["events"].append(event)
            except Exception as e:
                logger.error(f"Error appending research_init event: {e}")
        
        yield event

        event_background = {}

        # 搜索事件背景信息
        msg += f"\n🔍 搜索事件背景: {topic}"
        logger.info(f"Starting event background search for {topic}")
        
        # Emit search start event
        event = {
            "type": "background_search_start",
            "topic": topic,
            "message": f"搜索事件背景信息: {topic}",
            "step": "事件背景搜索"
        }
        
        if job_id:
            try:
                if job_id in job_status:
                    job_status[job_id]["events"].append(event)
            except Exception as e:
                logger.error(f"Error appending background_search_start event: {e}")
        
        yield event

        try:
            logger.info("Initiating Tavily search for event background")
            
            # 搜索事件基本信息
            search_result = await self.tavily_client.search(
                query=f"{topic} 事件详情 背景",
                search_depth="basic",  # Changed from advanced for speed
                max_results=5  # Reduced from 10 for speed
            )
            
            for item in search_result.get("results", []):
                if item.get("content"):
                    url = item.get("url", "")
                    event_background[url] = {
                        'title': item.get('title', ''),
                        'content': item.get('content', ''),
                        'url': url,
                        'source': 'background_search',
                        'score': item.get('score', 0.0)
                    }
            
            if event_background:
                logger.info(f"Successfully found {len(event_background)} background documents")
                msg += f"\n✅ 找到 {len(event_background)} 份背景文档"
                yield {
                    "type": "background_search_success",
                    "docs_found": len(event_background),
                    "message": f"找到 {len(event_background)} 份背景文档",
                    "step": "事件背景搜索"
                }
            else:
                logger.warning("No background content found")
                msg += "\n⚠️ 未找到背景信息"
                yield {
                    "type": "background_search_warning",
                    "message": "⚠️ 未找到事件背景信息",
                    "step": "事件背景搜索"
                }
        except Exception as e:
            error_str = str(e)
            logger.error(f"Background search error: {error_str}", exc_info=True)
            error_msg = f"⚠️ 搜索事件背景时出错: {error_str}"
            msg += f"\n{error_msg}"
            yield {
                "type": "background_search_error",
                "error": error_str,
                "message": error_msg,
                "step": "事件背景搜索",
                "continue_research": True
            }

        # Add context about what information we have
        context_data = {}
        if event_category := state.get('event_category'):
            msg += f"\n📂 事件类别: {event_category}"
            context_data["event_category"] = event_category
        if target_date := state.get('target_date'):
            msg += f"\n📅 预期结算日期: {target_date}"
            context_data["target_date"] = target_date
        if event_description := state.get('event_description'):
            msg += f"\n📝 事件描述: {event_description[:100]}..."
            context_data["event_description"] = event_description
        
        # Initialize ResearchState with input information
        research_state = {
            # Copy input fields
            "topic": state.get('topic'),
            "event_description": state.get('event_description'),
            "event_category": state.get('event_category'),
            "target_date": state.get('target_date'),
            "job_id": state.get('job_id'),
            # Initialize research fields
            "messages": [AIMessage(content=msg)],
            "event_background": event_background
        }

        yield {"type": "grounding_complete", "background_docs": len(event_background)}
        yield research_state

    async def run(self, state: InputState) -> ResearchState:
        """Run grounding - note: for now returns directly, events can be captured if needed"""
        result = None
        async for event in self.initial_search(state):
            if isinstance(event, dict) and "type" not in event:
                result = event
        return result if result else {}
