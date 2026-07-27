"""Multi-agent LangGraph for the Career Path Advisor profile collection pipeline.

The graph orchestrates 4 functional nodes:

    Extractor (LLM) -> Mapper (LLM) -> Orchestrator (Python) -> Writer (LLM)

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

# Global instance -- injected during FastAPI lifespan startup
_profile_graph_instance = None


def set_profile_graph_instance(graph: Any) -> None:
    """Inject a compiled graph instance (called from FastAPI lifespan)."""
    global _profile_graph_instance
    _profile_graph_instance = graph
    logger.info("PROFILE_GRAPH_INJECTED | nodes=4 | checkpointer=AsyncPostgresSaver")


def get_profile_graph() -> Any:
    """Return the compiled profile-collection graph."""
    if _profile_graph_instance is None:
        raise RuntimeError(
            "Profile graph has not been initialized. "
            "Ensure FastAPI lifespan startup has completed."
        )
    return _profile_graph_instance


def _should_skip_mapper(state: PipelineState) -> str:
    """Conditional edge: skip Mapper + Orchestrator if no data was extracted."""
    raw = state.extracted_raw.extracted if state.extracted_raw else {}
    if not raw:
        logger.info("GRAPH_SHORT_CIRCUIT | no extraction -> writer")
        return "writer"
    return "mapper"


async def build_profile_graph(checkpointer: Any) -> Any:
    """Construct and compile the LangGraph state machine."""
    builder = StateGraph(PipelineState)

    # Register nodes
    builder.add_node("extractor", extractor_node)
    builder.add_node("mapper", mapper_node)
    builder.add_node("orchestrator", orchestrator_node)
    builder.add_node("writer", writer_node)

    # Entry point
    builder.set_entry_point("extractor")

    # Extractor -> conditional: mapper (if data) or writer (if empty)
    builder.add_conditional_edges(
        "extractor",
        _should_skip_mapper,
        {
            "mapper": "mapper",
            "writer": "writer",
        },
    )

    # Normal flow
    builder.add_edge("mapper", "orchestrator")
    builder.add_edge("orchestrator", "writer")

    # Finish
    builder.add_edge("writer", END)

    compiled = builder.compile(checkpointer=checkpointer)
    logger.info("PROFILE_GRAPH_COMPILED | nodes=4 | checkpointer=AsyncPostgresSaver")
    return compiled


async def run_profile_pipeline(
    conversation_history: List[Dict[str, str]],
    thread_id: Optional[str] = None,
    collected_attributes: Optional[List[Any]] = None,
    db: Optional[AsyncSession] = None,
    conversation_id: Optional[UUID] = None,
) -> PipelineState:
    """Convenience runner: invoke the graph with an initial state.

    Args:
        conversation_history: Full user<->assistant message history.
        thread_id: Optional identifier for LangGraph checkpointing / threading.
        collected_attributes: Previously persisted attributes from the DB.
        db: Database session for the close-conversation tool.
        conversation_id: Conversation ID for the close-conversation tool.

    Returns:
        Final PipelineState after the graph completes (writer has responded).
    """
    graph = get_profile_graph()

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

    result = await graph.ainvoke(
        initial_state,
        config=config,
    )

    logger.info("PIPELINE_RUN_DONE | thread=%s", thread_id)

    return PipelineState.model_validate(result)
