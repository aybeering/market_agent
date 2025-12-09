import asyncio
import logging
import os
from datetime import datetime
from typing import Any, Dict, List

from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from tavily import AsyncTavilyClient

from ...classes import ResearchState
from ...classes.state import job_status
from ...utils.references import clean_title
from ...prompts import QUERY_FORMAT_GUIDELINES

logger = logging.getLogger(__name__)

class BaseResearcher:
    def __init__(self):
        tavily_key = os.getenv("TAVILY_API_KEY")
        openai_key = os.getenv("OPENAI_API_KEY")
        openai_base = os.getenv("OPENAI_BASE_URL", "http://4.216.184.165:3000/v1")
        
        if not tavily_key or not openai_key:
            raise ValueError("Missing API keys")
            
        self.tavily_client = AsyncTavilyClient(api_key=tavily_key)
        self.llm = ChatOpenAI(
            model="gpt-4o",
            temperature=0,
            streaming=True,
            api_key=openai_key,
            base_url=openai_base
        )
        self.analyst_type = "base_researcher"

    @property
    def analyst_type(self) -> str:
        if not hasattr(self, '_analyst_type'):
            raise ValueError("Analyst type not set by subclass")
        return self._analyst_type

    @analyst_type.setter
    def analyst_type(self, value: str):
        self._analyst_type = value

    async def generate_queries(self, state: Dict, prompt: str):
        """Generate search queries and yield events as they're created"""
        topic = state.get("topic", "Unknown Topic")
        event_category = state.get("event_category", "Unknown Category")
        target_date = state.get("target_date", "Unknown")
        current_year = datetime.now().year
        job_id = state.get("job_id")
        
        logger.info(f"=== GENERATE_QUERIES START: analyst={self.analyst_type} ===")
        
        try:
            # Create prompt template using LangChain
            query_prompt = ChatPromptTemplate.from_messages([
                ("system", "你正在研究事件'{topic}'，这是一个{event_category}类别的事件，预期结算日期为{target_date}。"),
                ("user", """研究事件 {topic}，当前时间 {year}年，日期 {date}。
{task_prompt}
{format_guidelines}""")
            ])
            
            # Create LCEL chain and invoke (non-streaming for speed)
            chain = query_prompt | self.llm
            
            result = await chain.ainvoke({
                "topic": topic,
                "event_category": event_category,
                "target_date": target_date,
                "year": current_year,
                "date": datetime.now().strftime("%Y年%m月%d日"),
                "task_prompt": prompt,
                "format_guidelines": QUERY_FORMAT_GUIDELINES.format(topic=topic)
            })
            
            # Parse queries from response
            queries = [q.strip() for q in result.content.strip().split('\n') if q.strip()]
            
            if not queries:
                raise ValueError(f"No queries generated for {topic}")

            queries = queries[:2]  # Limit to 2 queries for speed
            logger.info(f"Generated {len(queries)} queries for {self.analyst_type}")
            
            # Yield final result
            for i, query in enumerate(queries, 1):
                yield {"type": "query_generated", "query": query, "query_number": i, "category": self.analyst_type}
            
            yield {"type": "queries_complete", "queries": queries, "count": len(queries)}
            
        except Exception as e:
            logger.error(f"Error generating queries for {topic}: {e}")
            raise RuntimeError(f"Fatal API error - query generation failed: {str(e)}") from e

    def _get_search_params(self) -> Dict[str, Any]:
        """Get search parameters based on analyst type"""
        params = {
            "search_depth": "basic",
            "include_raw_content": False,
            "max_results": 3  # Reduced for speed
        }
        
        topic_map = {
            "news_analyzer": "news",
            "financial_analyzer": "finance"
        }
        
        if topic := topic_map.get(self.analyst_type):
            params["topic"] = topic
            
        return params
    
    def _process_search_result(self, result: Dict[str, Any], query: str) -> Dict[str, Any]:
        """Process a single search result into standardized format"""
        if not result.get("content") or not result.get("url"):
            return {}
            
        url = result.get("url")
        title = clean_title(result.get("title", "")) if result.get("title") else ""
        
        # Reset empty or invalid titles
        if not title or title.lower() == url.lower():
            title = ""
        
        return {
            "title": title,
            "content": result.get("content", ""),
            "query": query,
            "url": url,
            "source": "web_search",
            "score": result.get("score", 0.0)
        }

    async def search_documents(self, state: ResearchState, queries: List[str]):
        """Execute all Tavily searches in parallel and yield events"""
        if not queries:
            logger.error("No valid queries to search")
            yield {"type": "error", "error": "No valid queries to search"}
            return

        # Yield start event
        yield {
            "type": "search_started",
            "message": f"Searching {len(queries)} queries",
            "total_queries": len(queries)
        }

        # Execute all searches in parallel
        search_params = self._get_search_params()
        search_tasks = [self.tavily_client.search(query, **search_params) for query in queries]

        try:
            results = await asyncio.gather(*search_tasks, return_exceptions=True)
        except Exception as e:
            logger.error(f"Error during parallel search execution: {e}")
            yield {"type": "error", "error": str(e)}
            return

        # Process and merge results
        merged_docs = {}
        for query, result in zip(queries, results):
            if isinstance(result, Exception):
                logger.error(f"Search failed for query '{query}': {result}")
                yield {"type": "query_error", "query": query, "error": str(result)}
                continue
                
            for item in result.get("results", []):
                if doc := self._process_search_result(item, query):
                    merged_docs[doc["url"]] = doc

        # Yield completion event
        yield {
            "type": "search_complete",
            "message": f"Found {len(merged_docs)} documents",
            "total_documents": len(merged_docs),
            "queries_processed": len(queries),
            "merged_docs": merged_docs
        }
