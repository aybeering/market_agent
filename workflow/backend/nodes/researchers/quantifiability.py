from langchain_core.messages import AIMessage

from ...classes import ResearchState
from ...prompts import QUANTIFIABILITY_QUERY_PROMPT
from .base import BaseResearcher


class QuantifiabilityAnalyzer(BaseResearcher):
    """分析事件的可量化性：能否被严格定义和量化"""
    
    def __init__(self) -> None:
        super().__init__()
        self.analyst_type = "quantifiability_analyzer"
    
    async def analyze(self, state: ResearchState):
        """分析事件可量化性并生成事件"""
        topic = state.get('topic', 'Unknown Topic')
        
        # Generate search queries and yield events
        queries = []
        async for event in self.generate_queries(state, QUANTIFIABILITY_QUERY_PROMPT):
            yield event
            if event.get("type") == "queries_complete":
                queries = event.get("queries", [])
        
        # Log subqueries
        subqueries_msg = "🔍 可量化性分析子查询:\n" + "\n".join([f"• {query}" for query in queries])
        state.setdefault('messages', []).append(AIMessage(content=subqueries_msg))
        
        # Start with event background data
        quantifiability_data = dict(state.get('event_background', {}))
        
        # Search and merge documents, yielding events
        documents = {}
        async for event in self.search_documents(state, queries):
            yield event
            if event.get("type") == "search_complete":
                documents = event.get("merged_docs", {})
        
        quantifiability_data.update(documents)
        
        # Update state
        completion_msg = f"📐 可量化性分析找到 {len(quantifiability_data)} 份文档，事件: {topic}"
        state.setdefault('messages', []).append(AIMessage(content=completion_msg))
        state['quantifiability_data'] = quantifiability_data
        
        yield {"type": "analysis_complete", "data_type": "quantifiability_data", "count": len(quantifiability_data)}
        yield {'message': [completion_msg], 'quantifiability_data': quantifiability_data}

    async def run(self, state: ResearchState):
        """Run analysis and yield all events"""
        result = None
        async for event in self.analyze(state):
            yield event
            if "message" in event or "quantifiability_data" in event:
                result = event
        yield result or {}
