from langchain_core.messages import AIMessage

from ...classes import ResearchState
from ...prompts import MARKET_DEMAND_QUERY_PROMPT
from .base import BaseResearcher


class MarketDemandAnalyzer(BaseResearcher):
    """分析市场需求：交易者兴趣和合约设计建议"""
    
    def __init__(self) -> None:
        super().__init__()
        self.analyst_type = "market_demand_analyzer"
    
    async def analyze(self, state: ResearchState):
        """分析市场需求并生成事件"""
        topic = state.get('topic', 'Unknown Topic')
        
        # Generate search queries and yield events
        queries = []
        async for event in self.generate_queries(state, MARKET_DEMAND_QUERY_PROMPT):
            yield event
            if event.get("type") == "queries_complete":
                queries = event.get("queries", [])
        
        # Log subqueries
        subqueries_msg = "🔍 市场需求分析子查询:\n" + "\n".join([f"• {query}" for query in queries])
        state.setdefault('messages', []).append(AIMessage(content=subqueries_msg))
        
        # Start with event background data
        market_demand_data = dict(state.get('event_background', {}))
        
        # Search and merge documents, yielding events
        documents = {}
        async for event in self.search_documents(state, queries):
            yield event
            if event.get("type") == "search_complete":
                documents = event.get("merged_docs", {})
        
        market_demand_data.update(documents)
        
        # Update state
        completion_msg = f"📊 市场需求分析找到 {len(market_demand_data)} 份文档，事件: {topic}"
        state.setdefault('messages', []).append(AIMessage(content=completion_msg))
        state['market_demand_data'] = market_demand_data
        
        yield {"type": "analysis_complete", "data_type": "market_demand_data", "count": len(market_demand_data)}
        yield {'message': [completion_msg], 'market_demand_data': market_demand_data}

    async def run(self, state: ResearchState):
        """Run analysis and yield all events"""
        result = None
        async for event in self.analyze(state):
            yield event
            if "message" in event or "market_demand_data" in event:
                result = event
        yield result or {}
