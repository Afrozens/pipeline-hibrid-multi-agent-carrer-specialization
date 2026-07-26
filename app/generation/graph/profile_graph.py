"""Multi-agent LangGraph for the Career Path Advisor profile collection pipeline.

The graph orchestrates 4 functional nodes:

    Extractor (LLM) → Mapper (LLM) → Orchestrator (Python) → Writer (LLM)

Where:
  - Extractor: reads user message + history, extracts career profile fields
  - Mapper: normalizes colloquial values to canonical keys
  - Orchestrator: merges historical + new attributes, validates against
    career_fields.json, determines next field to ask
  - Writer: generates warm human response, asks for next field,
    calls close_conversation tool when profile is complete

Checkpointing via AsyncPostgresSaver for persistent conversation state.
"""

import logging
from typing import Any, Dict, List, Optional
from uuid import UUID

from langgraph.graph import StateGraph, END
from sqlalchemy.ext.asyncio import AsyncSession

from app.generation.schemas.agent_pipeline import PipelineState
from app.generation.services.extractor_service import extractor_node
from app.generation.services.mapper_service import mapper_node
from app.generation.services.orchestrator_service import orchestrator_node
from app.generation.services.writer_service import writer_node

logger = logging.getLogger(__name__)


class ProfilePipeline:
    def __init__(self, checkpointer: Any):
        self._checkpointer = checkpointer
        self._compiled_graph = self._build(checkpointer)

    def _should_skip_mapper(self, state: PipelineState) -> str:
        raw = state.extracted_raw.extracted if state.extracted_raw else {}
        if not raw:
            logger.info("GRAPH_SHORT_CIRCUIT | no extraction → writer")
            return "writer"
        return "mapper"

    def _build(self, checkpointer: Any) -> Any:
        builder = StateGraph(PipelineState)

        builder.add_node("extractor", extractor_node)
        builder.add_node("mapper", mapper_node)
        builder.add_node("orchestrator", orchestrator_node)
        builder.add_node("writer", writer_node)

        builder.set_entry_point("extractor")

        builder.add_conditional_edges(
            "extractor",
            self._should_skip_mapper,
            {
                "mapper": "mapper",
                "writer": "writer",
            },
        )

        builder.add_edge("mapper", "orchestrator")
        builder.add_edge("orchestrator", "writer")
        builder.add_edge("writer", END)

        compiled = builder.compile(checkpointer=checkpointer)
        logger.info("PROFILE_GRAPH_COMPILED | nodes=4 | checkpointer=AsyncPostgresSaver")
        return compiled

    async def run(
        self,
        conversation_history: List[Dict[str, str]],
        thread_id: Optional[str] = None,
        collected_attributes: Optional[List[Any]] = None,
        db: Optional[AsyncSession] = None,
        conversation_id: Optional[UUID] = None,
    ) -> PipelineState:
        initial_state = PipelineState(
            conversation_history=conversation_history,
            collected_attributes=collected_attributes or [],
        )

        config = {
            "configurable": {
                "thread_id": thread_id or "default",
                "db": db,
                "conversation_id": conversation_id,
            }
        }

        logger.info(
            "PIPELINE_RUN_START | thread=%s | turns=%d",
            thread_id,
            len(conversation_history),
        )

        result = await self._compiled_graph.ainvoke(
            initial_state,
            config=config,
        )

        logger.info("PIPELINE_RUN_DONE | thread=%s", thread_id)

        return PipelineState.model_validate(result)
