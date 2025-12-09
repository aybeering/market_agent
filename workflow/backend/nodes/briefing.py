import asyncio
import logging
import os
from typing import Any, Dict, List, Union

from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

from ..classes import ResearchState
from ..classes.state import job_status
from ..prompts import (
    QUANTIFIABILITY_BRIEFING_PROMPT,
    ORACLE_BRIEFING_PROMPT,
    MARKET_DEMAND_BRIEFING_PROMPT,
    COMPLIANCE_RISK_BRIEFING_PROMPT,
    BRIEFING_ANALYSIS_INSTRUCTION
)

logger = logging.getLogger(__name__)

class Briefing:
    """为每个分析维度创建简报并更新 ResearchState。"""
    
    def __init__(self) -> None:
        self.max_doc_length = 8000  # Maximum document content length
        openai_key = os.getenv("OPENAI_API_KEY")
        openai_base = os.getenv("OPENAI_BASE_URL", "http://4.216.184.165:3000/v1")
        if not openai_key:
            raise ValueError("OPENAI_API_KEY environment variable is not set")
        
        self.llm = ChatOpenAI(
            model="gpt-4o",
            temperature=0,
            api_key=openai_key,
            base_url=openai_base
        )

    def _get_category_prompt(self, category: str) -> str:
        """获取特定分析维度的 prompt 模板"""
        prompts = {
            'quantifiability': QUANTIFIABILITY_BRIEFING_PROMPT,
            'oracle': ORACLE_BRIEFING_PROMPT,
            'market_demand': MARKET_DEMAND_BRIEFING_PROMPT,
            'compliance_risk': COMPLIANCE_RISK_BRIEFING_PROMPT,
        }
        return prompts.get(category, 
                          "基于提供的文档，为事件'{topic}'创建一份专业的可行性分析简报。")
    
    def _prepare_documents(self, docs: Union[Dict[str, Any], List[Dict[str, Any]]]) -> str:
        """准备和格式化文档用于简报生成"""
        # Normalize docs to list of (url, doc) tuples
        items = list(docs.items()) if isinstance(docs, dict) else [
            (doc.get('url', f'doc_{i}'), doc) for i, doc in enumerate(docs)
        ]
        
        # Sort by evaluation score
        sorted_items = sorted(
            items, 
            key=lambda x: float(x[1].get('evaluation', {}).get('overall_score', '0')), 
            reverse=True
        )
        
        # Format documents with length limits
        doc_texts = []
        total_length = 0
        for _, doc in sorted_items:
            title = doc.get('title', '')
            content = doc.get('raw_content') or doc.get('content', '')
            
            if len(content) > self.max_doc_length:
                content = content[:self.max_doc_length] + "... [内容已截断]"
            
            doc_entry = f"标题: {title}\n\n内容: {content}"
            if total_length + len(doc_entry) < 120000:  # Keep under limit
                doc_texts.append(doc_entry)
                total_length += len(doc_entry)
            else:
                break
        
        separator = "\n" + "-" * 40 + "\n"
        return f"{separator}{separator.join(doc_texts)}{separator}"

    async def generate_category_briefing(
        self, docs: Union[Dict[str, Any], List[Dict[str, Any]]], 
        category: str, context: Dict[str, Any]
    ):
        """生成特定维度的简报并发出事件"""
        topic = context.get('topic', 'Unknown')
        event_category = context.get('event_category', 'Unknown')
        target_date = context.get('target_date', 'Unknown')
        job_id = context.get('job_id')
        
        logger.info(f"Generating {category} briefing for {topic} using {len(docs)} documents")

        # Emit briefing start event
        event = {
            "type": "briefing_start",
            "category": category,
            "total_docs": len(docs),
            "step": "简报生成"
        }
        
        if job_id:
            try:
                if job_id in job_status:
                    job_status[job_id]["events"].append(event)
            except Exception as e:
                logger.error(f"Error appending briefing_start event: {e}")
        
        yield event

        # Get category-specific prompt and prepare documents
        category_prompt = self._get_category_prompt(category).format(
            topic=topic, event_category=event_category, target_date=target_date
        )
        formatted_docs = self._prepare_documents(docs)
        
        # Create LCEL chain for briefing generation
        briefing_prompt = ChatPromptTemplate.from_messages([
            ("user", """{category_prompt}

{instruction}

{documents}""")
        ])
        
        chain = briefing_prompt | self.llm | StrOutputParser()
        
        try:
            logger.info("Sending prompt to LLM")
            content = await chain.ainvoke({
                "category_prompt": category_prompt,
                "instruction": BRIEFING_ANALYSIS_INSTRUCTION,
                "documents": formatted_docs
            })
            
            if not content:
                logger.error(f"Empty response from LLM for {category} briefing")
                yield {"type": "error", "error": "Empty response from LLM", "category": category}
                yield {'content': ''}
                return

            # Emit completion event
            event = {
                "type": "briefing_complete",
                "category": category,
                "content_length": len(content),
                "step": "简报生成"
            }
            
            if job_id:
                try:
                    if job_id in job_status:
                        job_status[job_id]["events"].append(event)
                except Exception as e:
                    logger.error(f"Error appending briefing_complete event: {e}")
            
            yield event
            yield {'content': content.strip()}
        except Exception as e:
            logger.error(f"Error generating {category} briefing: {e}")
            raise RuntimeError(f"Fatal API error - {category} briefing generation failed: {str(e)}") from e

    async def create_briefings(self, state: ResearchState) -> ResearchState:
        """并行创建所有维度的简报。"""
        topic = state.get('topic', 'Unknown Topic')
        logger.info(f"Creating section briefings for {topic}")
        
        context = {
            "topic": topic,
            "event_category": state.get('event_category', 'Unknown'),
            "target_date": state.get('target_date', 'Unknown'),
            "job_id": state.get('job_id')
        }
        
        # Mapping of curated data fields to briefing categories
        categories = {
            'quantifiability_data': ("quantifiability", "quantifiability_briefing"),
            'oracle_data': ("oracle", "oracle_briefing"),
            'market_demand_data': ("market_demand", "market_demand_briefing"),
            'compliance_risk_data': ("compliance_risk", "compliance_risk_briefing")
        }
        
        briefings = {}

        # Create tasks for parallel processing
        briefing_tasks = []
        for data_field, (cat, briefing_key) in categories.items():
            curated_key = f'curated_{data_field}'
            curated_data = state.get(curated_key, {})
            
            if curated_data:
                logger.info(f"Processing {data_field} with {len(curated_data)} documents")
                briefing_tasks.append({
                    'category': cat,
                    'briefing_key': briefing_key,
                    'data_field': data_field,
                    'curated_data': curated_data
                })
            else:
                logger.info(f"No data available for {data_field}")
                state[briefing_key] = ""

        # Process briefings in parallel with rate limiting
        if briefing_tasks:
            briefing_semaphore = asyncio.Semaphore(4)  # Allow all 4 briefings in parallel
            
            async def process_briefing(task: Dict[str, Any]) -> Dict[str, Any]:
                """Process a single briefing with rate limiting."""
                async with briefing_semaphore:
                    result = {'content': ''}
                    
                    async for event in self.generate_category_briefing(
                        task['curated_data'],
                        task['category'],
                        context
                    ):
                        if isinstance(event, dict) and 'content' in event:
                            result = event
                    
                    if result['content']:
                        briefings[task['category']] = result['content']
                        state[task['briefing_key']] = result['content']
                        logger.info(f"Completed {task['data_field']} briefing ({len(result['content'])} characters)")
                    else:
                        raise RuntimeError(f"Empty briefing generated for {task['data_field']}")
                    
                    return {
                        'category': task['category'],
                        'success': bool(result['content']),
                        'length': len(result['content']) if result['content'] else 0
                    }

            # Process all briefings in parallel
            results = await asyncio.gather(*[
                process_briefing(task) 
                for task in briefing_tasks
            ])
            
            # Log completion statistics
            successful_briefings = sum(1 for r in results if r['success'])
            total_length = sum(r['length'] for r in results)
            logger.info(f"Generated {successful_briefings}/{len(briefing_tasks)} briefings with total length {total_length}")

        state['briefings'] = briefings
        return state

    async def run(self, state: ResearchState) -> ResearchState:
        return await self.create_briefings(state)
