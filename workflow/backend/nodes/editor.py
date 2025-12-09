import logging
import os
from typing import Dict

from langchain_core.messages import AIMessage
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

from ..classes import ResearchState
from ..classes.state import job_status
from ..utils.references import format_references_section
from ..prompts import (
    EDITOR_SYSTEM_MESSAGE,
    COMPILE_CONTENT_PROMPT,
    CONTENT_SWEEP_SYSTEM_MESSAGE,
    CONTENT_SWEEP_PROMPT
)

logger = logging.getLogger(__name__)

class Editor:
    """将各维度简报编译成完整的事件期货可行性报告。"""
    
    def __init__(self) -> None:
        openai_key = os.getenv("OPENAI_API_KEY")
        openai_base = os.getenv("OPENAI_BASE_URL", "http://4.216.184.165:3000/v1")
        if not openai_key:
            raise ValueError("OPENAI_API_KEY environment variable is not set")
        
        # Configure LangChain ChatOpenAI
        self.llm = ChatOpenAI(
            model="gpt-4o",
            temperature=0,
            streaming=True,
            api_key=openai_key,
            base_url=openai_base
        )
        
        # Initialize context dictionary
        self.context = {
            "topic": "Unknown Topic",
            "event_category": "Unknown",
            "target_date": "Unknown"
        }

    async def compile_briefings(self, state: ResearchState) -> ResearchState:
        """将各维度简报编译成最终的可行性报告。"""
        topic = state.get('topic', 'Unknown Topic')
        job_id = state.get('job_id')
        
        # Update context with values from state
        self.context = {
            "topic": topic,
            "event_category": state.get('event_category', 'Unknown'),
            "target_date": state.get('target_date', 'Unknown')
        }
        
        msg = [f"📑 正在编译事件期货可行性报告: {topic}..."]
        
        # Emit report compilation start event
        if job_id:
            try:
                if job_id in job_status:
                    job_status[job_id]["events"].append({
                        "type": "report_compilation",
                        "message": f"正在编译可行性报告: {topic}"
                    })
            except Exception as e:
                logger.error(f"Error appending report_compilation event: {e}")
        
        # Pull individual briefings from dedicated state keys
        briefing_keys = {
            'quantifiability': 'quantifiability_briefing',
            'oracle': 'oracle_briefing',
            'market_demand': 'market_demand_briefing',
            'compliance_risk': 'compliance_risk_briefing'
        }

        individual_briefings = {}
        for category, key in briefing_keys.items():
            if content := state.get(key):
                individual_briefings[category] = content
                msg.append(f"找到 {category} 简报 ({len(content)} 字符)")
            else:
                msg.append(f"无 {category} 简报")
                logger.error(f"Missing state key: {key}")
        
        if not individual_briefings:
            msg.append("\n⚠️ 没有可用的简报章节进行编译")
            logger.error("No briefings found in state")
        else:
            try:
                compiled_report = await self.edit_report(state, individual_briefings)
                if not compiled_report or not compiled_report.strip():
                    logger.error("Compiled report is empty!")
                else:
                    logger.info(f"Successfully compiled report with {len(compiled_report)} characters")
            except Exception as e:
                logger.error(f"Error during report compilation: {e}")
        
        state.setdefault('messages', []).append(AIMessage(content="\n".join(msg)))
        return state
    
    async def edit_report(self, state: ResearchState, briefings: Dict[str, str]) -> str:
        """编译各维度简报生成最终报告并更新状态。"""
        try:
            logger.info("Starting report compilation")
            job_id = state.get('job_id')
            
            # Step 1: Initial Compilation
            edited_report = await self.compile_content(state, briefings)
            if not edited_report:
                logger.error("Initial compilation failed")
                return ""

            # Step 2 & 3: Content sweep and streaming
            final_report = ""
            async for event in self.content_sweep(edited_report):
                # Forward streaming events to job_status
                if isinstance(event, dict) and job_id:
                    try:
                        if job_id in job_status:
                            job_status[job_id]["events"].append(event)
                            logger.debug(f"Appended report_chunk event ({len(event.get('chunk', ''))} chars)")
                    except Exception as e:
                        logger.error(f"Error appending report_chunk event: {e}")
                
                # Accumulate the text
                if isinstance(event, str):
                    final_report = event
            
            final_report = final_report or edited_report or ""
            
            logger.info(f"Final report compiled with {len(final_report)} characters")
            if not final_report.strip():
                logger.error("Final report is empty!")
                return ""
            
            # Update state with the final report
            state['report'] = final_report
            state['status'] = "editor_complete"
            if 'editor' not in state or not isinstance(state['editor'], dict):
                state['editor'] = {}
            state['editor']['report'] = final_report
            
            return final_report
        except Exception as e:
            logger.error(f"Error in edit_report: {e}")
            return ""
    
    async def compile_content(self, state: ResearchState, briefings: Dict[str, str]) -> str:
        """使用 LCEL 进行初始编译。"""
        combined_content = "\n\n".join(content for content in briefings.values())
        
        references = state.get('references', [])
        reference_text = ""
        if references:
            logger.info(f"Found {len(references)} references to add during compilation")
            reference_info = state.get('reference_info', {})
            reference_titles = state.get('reference_titles', {})
            reference_text = format_references_section(references, reference_info, reference_titles)
            logger.info(f"Added {len(references)} references during compilation")
        
        # Create LCEL chain for compilation
        compile_prompt = ChatPromptTemplate.from_messages([
            ("system", EDITOR_SYSTEM_MESSAGE),
            ("user", COMPILE_CONTENT_PROMPT)
        ])
        
        chain = compile_prompt | self.llm | StrOutputParser()
        
        try:
            initial_report = await chain.ainvoke({
                "topic": self.context["topic"],
                "event_category": self.context["event_category"],
                "target_date": self.context["target_date"],
                "combined_content": combined_content
            })
            
            # Append references section
            if reference_text:
                initial_report = f"{initial_report}\n\n{reference_text}"
            
            return initial_report
        except Exception as e:
            logger.error(f"Error in initial compilation: {e}")
            return combined_content or ""
        
    async def content_sweep(self, content: str):
        """使用 LCEL 流式输出清理内容中的冗余信息。"""
        # Create LCEL chain for content sweep
        sweep_prompt = ChatPromptTemplate.from_messages([
            ("system", CONTENT_SWEEP_SYSTEM_MESSAGE),
            ("user", CONTENT_SWEEP_PROMPT)
        ])
        
        chain = sweep_prompt | self.llm | StrOutputParser()
        
        try:
            accumulated_text = ""
            buffer = ""
            
            # Stream using LangChain's astream
            async for chunk in chain.astream({
                "topic": self.context["topic"],
                "event_category": self.context["event_category"],
                "target_date": self.context["target_date"],
                "content": content
            }):
                accumulated_text += chunk
                buffer += chunk
                
                # Yield chunks at sentence boundaries
                if any(char in buffer for char in ['.', '!', '?', '\n', '。', '！', '？']) and len(buffer) > 10:
                    yield {"type": "report_chunk", "chunk": buffer, "step": "Editor"}
                    buffer = ""
            
            # Yield final buffer
            if buffer:
                yield {"type": "report_chunk", "chunk": buffer, "step": "Editor"}
            
            yield accumulated_text.strip()
        except Exception as e:
            logger.error(f"Error in formatting: {e}")
            yield {"type": "error", "error": str(e), "step": "Editor"}
            yield content or ""

    async def run(self, state: ResearchState) -> ResearchState:
        state = await self.compile_briefings(state)
        # Ensure the Editor node's output is stored both top-level and under "editor"
        if 'report' in state:
            if 'editor' not in state or not isinstance(state['editor'], dict):
                state['editor'] = {}
            state['editor']['report'] = state['report']
        return state
