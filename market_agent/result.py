"""
SearchResult - 搜索结果的结构化对象
"""

from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any


@dataclass
class SearchResult:
    """
    事件期货可行性分析的结构化结果
    
    Attributes:
        success: 是否成功完成分析
        topic: 分析的事件话题
        report: 完整的可行性报告 (Markdown 格式)
        feasibility_score: 综合可行性评分 (0-10)
        event_category: 事件类别
        target_date: 预期结算日期
        job_id: 任务ID
        
        # 各维度简报
        quantifiability_briefing: 可量化性简报
        oracle_briefing: 预言机简报
        market_demand_briefing: 市场需求简报
        compliance_risk_briefing: 合规风险简报
        
        # 元数据
        references: 引用来源列表
        elapsed_time: 执行耗时(秒)
        error: 错误信息 (如果失败)
        error_details: 详细错误信息
    """
    
    # 核心字段
    success: bool = False
    topic: str = ""
    report: str = ""
    feasibility_score: Optional[float] = None
    
    # 输入参数
    event_category: Optional[str] = None
    target_date: Optional[str] = None
    job_id: str = ""
    
    # 各维度简报
    quantifiability_briefing: str = ""
    oracle_briefing: str = ""
    market_demand_briefing: str = ""
    compliance_risk_briefing: str = ""
    
    # 元数据
    references: List[str] = field(default_factory=list)
    elapsed_time: float = 0.0
    
    # 错误信息
    error: Optional[str] = None
    error_details: Optional[Dict[str, Any]] = None
    
    def __repr__(self) -> str:
        if self.success:
            return (
                f"SearchResult(success=True, topic='{self.topic[:50]}...', "
                f"feasibility_score={self.feasibility_score}, "
                f"report_length={len(self.report)})"
            )
        else:
            return f"SearchResult(success=False, error='{self.error}')"
    
    def __bool__(self) -> bool:
        """允许直接用 if result: 判断是否成功"""
        return self.success
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            "success": self.success,
            "topic": self.topic,
            "report": self.report,
            "feasibility_score": self.feasibility_score,
            "event_category": self.event_category,
            "target_date": self.target_date,
            "job_id": self.job_id,
            "quantifiability_briefing": self.quantifiability_briefing,
            "oracle_briefing": self.oracle_briefing,
            "market_demand_briefing": self.market_demand_briefing,
            "compliance_risk_briefing": self.compliance_risk_briefing,
            "references": self.references,
            "elapsed_time": self.elapsed_time,
            "error": self.error,
            "error_details": self.error_details,
        }
    
    @classmethod
    def from_error(
        cls, 
        error: str, 
        topic: str = "", 
        job_id: str = "",
        error_details: Optional[Dict[str, Any]] = None
    ) -> "SearchResult":
        """创建一个错误结果"""
        return cls(
            success=False,
            topic=topic,
            job_id=job_id,
            error=error,
            error_details=error_details
        )
    
    @classmethod
    def from_state(cls, state: Dict[str, Any], job_id: str, elapsed_time: float, topic: str = "") -> "SearchResult":
        """从工作流状态创建结果"""
        # 提取报告 - 需要从嵌套的 editor 字典中提取
        report = ""
        
        # state 可能是 {"editor": {"report": "..."}} 格式
        if "editor" in state and isinstance(state["editor"], dict):
            report = state["editor"].get("report", "")
            # 从 editor 状态中提取其他字段
            editor_state = state["editor"]
            inner_topic = editor_state.get("topic", "")
            feasibility_score = editor_state.get("feasibility_score")
            event_category = editor_state.get("event_category")
            target_date = editor_state.get("target_date")
            quantifiability_briefing = editor_state.get("quantifiability_briefing", "")
            oracle_briefing = editor_state.get("oracle_briefing", "")
            market_demand_briefing = editor_state.get("market_demand_briefing", "")
            compliance_risk_briefing = editor_state.get("compliance_risk_briefing", "")
            references = editor_state.get("references", [])
        else:
            # 直接从 state 提取
            report = state.get("report", "")
            inner_topic = state.get("topic", "")
            feasibility_score = state.get("feasibility_score")
            event_category = state.get("event_category")
            target_date = state.get("target_date")
            quantifiability_briefing = state.get("quantifiability_briefing", "")
            oracle_briefing = state.get("oracle_briefing", "")
            market_demand_briefing = state.get("market_demand_briefing", "")
            compliance_risk_briefing = state.get("compliance_risk_briefing", "")
            references = state.get("references", [])
        
        # 使用传入的 topic 作为备选
        final_topic = inner_topic or topic
        
        if not report:
            return cls.from_error(
                error="工作流完成但未生成报告",
                topic=final_topic,
                job_id=job_id
            )
        
        return cls(
            success=True,
            topic=final_topic,
            report=report,
            feasibility_score=feasibility_score,
            event_category=event_category,
            target_date=target_date,
            job_id=job_id,
            quantifiability_briefing=quantifiability_briefing,
            oracle_briefing=oracle_briefing,
            market_demand_briefing=market_demand_briefing,
            compliance_risk_briefing=compliance_risk_briefing,
            references=references if isinstance(references, list) else [],
            elapsed_time=elapsed_time
        )
