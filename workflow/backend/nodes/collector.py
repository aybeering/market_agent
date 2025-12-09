from langchain_core.messages import AIMessage

from ..classes import ResearchState


class Collector:
    """收集和整理所有分析数据。"""

    async def collect(self, state: ResearchState) -> ResearchState:
        """收集并验证所有分析数据。"""
        topic = state.get('topic', 'Unknown Topic')
        msg = [f"📦 收集事件分析数据: {topic}:"]
        
        # Check each type of analysis data
        analysis_types = {
            'quantifiability_data': '📐 可量化性',
            'oracle_data': '🔮 预言机',
            'market_demand_data': '📊 市场需求',
            'compliance_risk_data': '⚖️ 合规风险'
        }
        
        for data_field, label in analysis_types.items():
            data = state.get(data_field, {})
            if data:
                msg.append(f"• {label}: 收集到 {len(data)} 份文档")
            else:
                msg.append(f"• {label}: 未找到数据")
        
        # Update state with collection message
        state.setdefault('messages', []).append(AIMessage(content="\n".join(msg)))
        
        return state

    async def run(self, state: ResearchState) -> ResearchState:
        return await self.collect(state)
