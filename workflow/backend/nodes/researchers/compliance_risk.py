from langchain_core.messages import AIMessage

from ...classes import ResearchState
from ...prompts import COMPLIANCE_RISK_QUERY_PROMPT
from .base import BaseResearcher


class ComplianceRiskAnalyzer(BaseResearcher):
    """分析合规与风险：法律、伦理和操纵风险评估"""
    
    def __init__(self) -> None:
        super().__init__()
        self.analyst_type = "compliance_risk_analyzer"
    
    async def analyze(self, state: ResearchState):
        """分析合规风险并生成事件"""
        topic = state.get('topic', 'Unknown Topic')
        
        # Generate search queries and yield events
        queries = []
        async for event in self.generate_queries(state, COMPLIANCE_RISK_QUERY_PROMPT):
            yield event
            if event.get("type") == "queries_complete":
                queries = event.get("queries", [])
        
        # Log subqueries
        subqueries_msg = "🔍 合规风险分析子查询:\n" + "\n".join([f"• {query}" for query in queries])
        state.setdefault('messages', []).append(AIMessage(content=subqueries_msg))
        
        # Start with event background data
        compliance_risk_data = dict(state.get('event_background', {}))
        
        # Search and merge documents, yielding events
        documents = {}
        async for event in self.search_documents(state, queries):
            yield event
            if event.get("type") == "search_complete":
                documents = event.get("merged_docs", {})
        
        compliance_risk_data.update(documents)
        
        # Update state
        completion_msg = f"⚖️ 合规风险分析找到 {len(compliance_risk_data)} 份文档，事件: {topic}"
        state.setdefault('messages', []).append(AIMessage(content=completion_msg))
        state['compliance_risk_data'] = compliance_risk_data
        
        yield {"type": "analysis_complete", "data_type": "compliance_risk_data", "count": len(compliance_risk_data)}
        yield {'message': [completion_msg], 'compliance_risk_data': compliance_risk_data}

    async def run(self, state: ResearchState):
        """Run analysis and yield all events"""
        result = None
        async for event in self.analyze(state):
            yield event
            if "message" in event or "compliance_risk_data" in event:
                result = event
        yield result or {}
