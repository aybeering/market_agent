import logging
from typing import Any, AsyncIterator, Dict

from langchain_core.messages import SystemMessage
from langgraph.graph import StateGraph

from .classes.state import InputState
from .nodes import GroundingNode
from .nodes.briefing import Briefing
from .nodes.collector import Collector
from .nodes.curator import Curator
from .nodes.editor import Editor
from .nodes.enricher import Enricher
from .nodes.researchers import (
    QuantifiabilityAnalyzer,
    OracleAnalyzer,
    MarketDemandAnalyzer,
    ComplianceRiskAnalyzer,
)

logger = logging.getLogger(__name__)

class Graph:
    def __init__(self, topic=None, event_description=None, event_category=None, target_date=None, job_id=None):
        # Initialize InputState for Event Futures Feasibility Analysis
        self.input_state = InputState(
            topic=topic,
            event_description=event_description,
            event_category=event_category,
            target_date=target_date,
            job_id=job_id,
            messages=[
                SystemMessage(content="开始事件期货可行性分析")
            ]
        )

        # Initialize nodes
        self._init_nodes()
        self._build_workflow()

    def _init_nodes(self):
        """Initialize all workflow nodes"""
        self.ground = GroundingNode()
        self.quantifiability_analyzer = QuantifiabilityAnalyzer()
        self.oracle_analyzer = OracleAnalyzer()
        self.market_demand_analyzer = MarketDemandAnalyzer()
        self.compliance_risk_analyzer = ComplianceRiskAnalyzer()
        self.collector = Collector()
        self.curator = Curator()
        self.enricher = Enricher()
        self.briefing = Briefing()
        self.editor = Editor()

    def _build_workflow(self):
        """Configure the state graph workflow"""
        self.workflow = StateGraph(InputState)
        
        # Add nodes with their respective processing functions
        self.workflow.add_node("grounding", self.ground.run)
        self.workflow.add_node("quantifiability_analyzer", self.quantifiability_analyzer.run)
        self.workflow.add_node("oracle_analyzer", self.oracle_analyzer.run)
        self.workflow.add_node("market_demand_analyzer", self.market_demand_analyzer.run)
        self.workflow.add_node("compliance_risk_analyzer", self.compliance_risk_analyzer.run)
        self.workflow.add_node("collector", self.collector.run)
        self.workflow.add_node("curator", self.curator.run)
        self.workflow.add_node("enricher", self.enricher.run)
        self.workflow.add_node("briefing", self.briefing.run)
        self.workflow.add_node("editor", self.editor.run)

        # Configure workflow edges
        self.workflow.set_entry_point("grounding")
        self.workflow.set_finish_point("editor")
        
        # Four parallel analysis nodes
        analysis_nodes = [
            "quantifiability_analyzer",   # 可量化性分析
            "oracle_analyzer",            # 预言机分析
            "market_demand_analyzer",     # 市场需求分析
            "compliance_risk_analyzer"    # 合规风险分析
        ]

        # Connect grounding to all analysis nodes (fan-out)
        for node in analysis_nodes:
            self.workflow.add_edge("grounding", node)
            self.workflow.add_edge(node, "collector")

        # Connect remaining nodes (sequential pipeline)
        self.workflow.add_edge("collector", "curator")
        self.workflow.add_edge("curator", "enricher")
        self.workflow.add_edge("enricher", "briefing")
        self.workflow.add_edge("briefing", "editor")

    async def run(self, thread: Dict[str, Any]) -> AsyncIterator[Dict[str, Any]]:
        """Execute the feasibility analysis workflow"""
        compiled_graph = self.workflow.compile()
        
        async for state in compiled_graph.astream(
            self.input_state,
            thread
        ):
            yield state
    
    def compile(self):
        graph = self.workflow.compile()
        return graph
