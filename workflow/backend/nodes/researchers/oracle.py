from langchain_core.messages import AIMessage

from ...classes import ResearchState
from ...prompts import ORACLE_QUERY_PROMPT
from .base import BaseResearcher


class OracleAnalyzer(BaseResearcher):
    """分析预言机与结算机制：可信数据源和结算可靠性"""
    
    def __init__(self) -> None:
        super().__init__()
        self.analyst_type = "oracle_analyzer"
    
    async def analyze(self, state: ResearchState):
        """分析预言机和结算机制并生成事件"""
        topic = state.get('topic', 'Unknown Topic')
        
        # Generate search queries and yield events
        queries = []
        async for event in self.generate_queries(state, ORACLE_QUERY_PROMPT):
            yield event
            if event.get("type") == "queries_complete":
                queries = event.get("queries", [])
        
        # Log subqueries
        subqueries_msg = "🔍 预言机分析子查询:\n" + "\n".join([f"• {query}" for query in queries])
        state.setdefault('messages', []).append(AIMessage(content=subqueries_msg))
        
        # Start with event background data
        oracle_data = dict(state.get('event_background', {}))
        
        # Search and merge documents, yielding events
        documents = {}
        async for event in self.search_documents(state, queries):
            yield event
            if event.get("type") == "search_complete":
                documents = event.get("merged_docs", {})
        
        oracle_data.update(documents)
        
        # Update state
        completion_msg = f"🔮 预言机分析找到 {len(oracle_data)} 份文档，事件: {topic}"
        state.setdefault('messages', []).append(AIMessage(content=completion_msg))
        state['oracle_data'] = oracle_data
        
        yield {"type": "analysis_complete", "data_type": "oracle_data", "count": len(oracle_data)}
        yield {'message': [completion_msg], 'oracle_data': oracle_data}

    async def run(self, state: ResearchState):
        """Run analysis and yield all events"""
        result = None
        async for event in self.analyze(state):
            yield event
            if "message" in event or "oracle_data" in event:
                result = event
        yield result or {}
