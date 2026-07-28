"""Pipeline integration layer for the Career Path Advisor.

Bridges the existing ``assistant_service`` interface (used by the
chat controller) with the new multi-agent LangGraph pipeline.
"""

import logging
from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.profile_student_attribute.schema import (
    ProfileStudentAttributeCreate,
)
from app.profile_student_attribute.utils import decrypt_if_sensitive
from app.generation.schemas.agent_pipeline import PipelineState
from app.generation.services.assistant_service import (
    generate_profile_assistant_response as _legacy_generate,
)

logger = logging.getLogger(__name__)


async def generate_profile_response_pipeline(
    *,
    conversation_history: List[Dict[str, str]],
    profile_attributes: Optional[List[Any]] = None,
    missing_fields: Optional[Dict[str, List[str]]] = None,
    thread_id: Optional[str] = None,
    db: Optional[AsyncSession] = None,
    conversation_id: Optional[UUID] = None,
) -> Tuple[str, str, List[ProfileStudentAttributeCreate], bool, bool]:
    collected_attributes: List[ProfileStudentAttributeCreate] = []
    if profile_attributes:
        for attr in profile_attributes:
            if getattr(attr, "deleted_at", None) is not None:
                continue
            plain_value = decrypt_if_sensitive(attr.key, attr.value)
            collected_attributes.append(
                ProfileStudentAttributeCreate(
                    category_name=attr.category_name,
                    key=attr.key,
                    value=plain_value,
                )
            )

    if thread_id is None:
        last_user_msg = None
        for entry in reversed(conversation_history):
            if entry.get("role") == "user":
                last_user_msg = entry.get("content", "")
                break
        thread_id = f"pipeline_{hash(last_user_msg) & 0xFFFFFFFF:08x}" if last_user_msg else "pipeline_default"

    try:
        from app.generation.graph import run_profile_pipeline
        
        final_state = await run_profile_pipeline(
            conversation_history=conversation_history,
            thread_id=thread_id,
            collected_attributes=collected_attributes,
            db=db,
            conversation_id=conversation_id,
        )
    except Exception as exc:
        logger.error(
            "PIPELINE_FAILED_FALLBACK | error=%s | thread=%s",
            exc,
            thread_id,
            exc_info=True,
        )
        legacy_result = await _legacy_generate(
            conversation_history=conversation_history,
            profile_attributes=profile_attributes,
            missing_fields=missing_fields or {},
        )
        return (*legacy_result, False, False)

    clean_text = final_state.assistant_response or ""
    raw_text = final_state.raw_llm_response or clean_text
    attr_creates = final_state.attributes_to_persist

    logger.info(
        "PIPELINE_SUCCESS | thread=%s | response_len=%d | attrs=%d | category=%s | profile_complete=%s | should_close=%s",
        thread_id,
        len(clean_text),
        len(attr_creates),
        final_state.current_category,
        final_state.profile_complete,
        final_state.should_close,
    )

    return clean_text, raw_text, attr_creates, final_state.profile_complete, final_state.should_close
