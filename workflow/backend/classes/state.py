from typing import TypedDict, NotRequired, Required, Dict, List, Any
from collections import defaultdict
from datetime import datetime

#Define the input state for Event Futures Feasibility Analysis
class InputState(TypedDict, total=False):
    topic: Required[str]                    # 事件话题 (如 "2024年美联储降息")
    event_description: NotRequired[str]     # 事件详细描述
    event_category: NotRequired[str]        # 事件类别 (政治/经济/体育/科技等)
    target_date: NotRequired[str]           # 预期结算日期
    job_id: NotRequired[str]

class ResearchState(InputState):
    # 初始搜索数据
    event_background: Dict[str, Any]        # 事件背景信息
    messages: List[Any]
    
    # 四个维度的原始分析数据
    quantifiability_data: Dict[str, Any]    # 可量化性分析数据
    oracle_data: Dict[str, Any]             # 预言机/结算机制数据
    market_demand_data: Dict[str, Any]      # 市场需求数据
    compliance_risk_data: Dict[str, Any]    # 合规风险数据
    
    # 筛选后的数据
    curated_quantifiability_data: Dict[str, Any]
    curated_oracle_data: Dict[str, Any]
    curated_market_demand_data: Dict[str, Any]
    curated_compliance_risk_data: Dict[str, Any]
    
    # 各维度简报
    quantifiability_briefing: str           # 可量化性简报
    oracle_briefing: str                    # 预言机简报
    market_demand_briefing: str             # 市场需求简报
    compliance_risk_briefing: str           # 合规风险简报
    
    # 最终输出
    references: List[str]
    briefings: Dict[str, Any]
    feasibility_score: float                # 综合可行性评分 (0-10)
    report: str                             # 最终可行性报告

# Global job status tracker - shared across application.py and backend nodes
job_status = defaultdict[Any, dict[str, str | list[Any] | None]](lambda: {
    "status": "pending",
    "result": None,
    "error": None,
    "debug_info": [],
    "company": None,
    "report": None,
    "last_update": datetime.now().isoformat(),
    "events": []  # Queue for events from parallel nodes
})