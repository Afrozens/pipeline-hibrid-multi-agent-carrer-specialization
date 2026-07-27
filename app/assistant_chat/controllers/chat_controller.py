import asyncio
import logging
import os
import tempfile
from uuid import UUID

from fastapi import HTTPException, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.assistant_chat.enums.message_role import MessageRole
from app.assistant_chat.schemas.chat import ChatResponse
from app.assistant_chat.schemas.message import AssistantMessageCreate, AssistantMessageResponse
from app.assistant_chat.services.chat_service import (
    close_conversation_service,
    create_and_link_profile,
    get_conversation_orm,
    get_profile_orm,
)
from app.assistant_chat.services.message_service import (
    create_message as svc_create_message,
    list_messages_by_conversation as svc_list_messages,
)
from app.core.config import get_settings
from app.profile_student.services.profile_student_service import (
    add_attributes_to_profile,
    validate_profile,
)
from app.profile_student.utils import CriticalFieldValidator
from app.generation.utils.attributes import unflatten_attributes
from app.generation.utils.formatting import determine_current_category, flatten_for_attributes
from app.generation.services.pipeline_service import generate_profile_response_pipeline
from app.generation.services.pdf_upload_service import (
    extract_fields_from_pdf_markdown,
    generate_pdf_upload_response,
)

logger = logging.getLogger(__name__)
settings = get_settings()
_validator = CriticalFieldValidator()


async def start_chat(db: AsyncSession, conversation_id: UUID) -> ChatResponse:
    conversation = await get_conversation_orm(db, conversation_id)
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")

    if conversation.profile_id is None:
        profile = await create_and_link_profile(db, conversation)
    else:
        profile = await get_profile_orm(db, conversation.profile_id)
        if not profile:
            raise HTTPException(status_code=404, detail="Linked profile not found")

    collected = _validator.validate_extracted_fields({})
    if profile.attributes:
        extracted = unflatten_attributes(profile.attributes)
        collected = _validator.validate_extracted_fields(extracted)

    welcome_text = (
        "Welcome to the Career Path Advisor! "
        "I'm here to help you build your career profile. "
        "To get started, could you please provide your full name?"
    )

    assistant_msg_raw = await svc_create_message(
        db,
        AssistantMessageCreate(
            conversation_id=conversation_id,
            role=MessageRole.ASSISTANT,
            content=welcome_text,
            model=settings.OPENAI_MODEL,
            message_metadata={"raw_content": welcome_text},
        ),
    )
    assistant_msg = AssistantMessageResponse.model_validate(assistant_msg_raw)

    updated_attrs = []
    profile_status = profile.status
    current_category = determine_current_category(collected)

    logger.info(
        "CHAT_START_DONE | conversation_id=%s | profile_id=%s | category=%s | status=%s",
        conversation_id,
        profile.id,
        current_category,
        profile_status,
    )

    return ChatResponse(
        assistant_message=assistant_msg,
        updated_attributes=updated_attrs,
        current_category=current_category,
        missing_fields=collected,
        profile_status=profile_status,
        profile_id=profile.id,
    )


async def chat(
    db: AsyncSession,
    conversation_id: UUID,
    message: str,
) -> ChatResponse:
    conversation = await get_conversation_orm(db, conversation_id)
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")

    if not conversation.profile_id:
        raise HTTPException(
            status_code=400,
            detail="Conversation has no linked profile. Call /chat/start first.",
        )

    profile = await get_profile_orm(db, conversation.profile_id)
    if not profile:
        raise HTTPException(status_code=404, detail="Linked profile not found")

    await svc_create_message(
        db,
        AssistantMessageCreate(
            conversation_id=conversation_id,
            role=MessageRole.USER,
            content=message,
        ),
    )

    db_messages = await svc_list_messages(db, conversation_id)
    history = []
    for m in db_messages:
        if m.role == MessageRole.ASSISTANT and m.message_metadata and m.message_metadata.get("raw_content"):
            history.append({"role": m.role, "content": m.message_metadata["raw_content"]})
        else:
            history.append({"role": m.role, "content": m.content or ""})

    extracted = unflatten_attributes(profile.attributes)
    collected = _validator.validate_extracted_fields(extracted)

    clean_text, raw_text, attr_creates, profile_complete, should_close = (
        await generate_profile_response_pipeline(
            conversation_history=history,
            profile_attributes=profile.attributes,
            missing_fields=collected,
            thread_id=str(conversation_id),
            db=db,
            conversation_id=conversation_id,
        )
    )

    updated_attrs = []
    if attr_creates:
        updated_attrs = await add_attributes_to_profile(db, profile.id, attr_creates)
        await db.commit()
        validation = await validate_profile(db, profile.id)
        collected = validation.missing_fields if validation else {}
        profile_status = validation.status if validation else profile.status
    else:
        profile_status = profile.status

    if should_close:
        await db.refresh(profile)
        conversation = await get_conversation_orm(db, conversation_id)
        profile_status = profile.status
        current_category = "complete"

        db_messages = await svc_list_messages(db, conversation_id)
        farewell_msg_raw = db_messages[-1] if db_messages else None
        assistant_msg = (
            AssistantMessageResponse.model_validate(farewell_msg_raw)
            if farewell_msg_raw
            else AssistantMessageResponse(
                role=MessageRole.ASSISTANT,
                content="Your profile has been finalized and the conversation is now closed. Thank you!",
            )
        )

        logger.info(
            "CHAT_CLOSED_VIA_TOOL | conversation_id=%s | profile_id=%s | status=%s",
            conversation_id,
            profile.id,
            profile_status,
        )
    else:
        assistant_msg_raw = await svc_create_message(
            db,
            AssistantMessageCreate(
                conversation_id=conversation_id,
                role=MessageRole.ASSISTANT,
                content=clean_text,
                model=settings.OPENAI_MODEL,
                message_metadata={"raw_content": raw_text},
            ),
        )
        assistant_msg = AssistantMessageResponse.model_validate(assistant_msg_raw)
        current_category = determine_current_category(collected)

    logger.info(
        "CHAT_TURN_DONE | conversation_id=%s | profile_id=%s | category=%s | new_attrs=%d | status=%s",
        conversation_id,
        profile.id,
        current_category,
        len(updated_attrs),
        profile_status,
    )

    return ChatResponse(
        assistant_message=assistant_msg,
        updated_attributes=updated_attrs,
        current_category=current_category,
        missing_fields=collected,
        profile_status=profile_status,
        profile_id=profile.id,
    )


async def upload_chat_pdf(
    db: AsyncSession,
    conversation_id: UUID,
    file: UploadFile,
) -> ChatResponse:
    conversation = await get_conversation_orm(db, conversation_id)
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")

    if not conversation.profile_id:
        raise HTTPException(
            status_code=400,
            detail="Conversation has no linked profile. Call /chat/start first.",
        )

    profile = await get_profile_orm(db, conversation.profile_id)
    if not profile:
        raise HTTPException(status_code=404, detail="Linked profile not found")

    filename = file.filename or "unknown.pdf"
    logger.info(
        "CHAT_UPLOAD_PDF_START | conversation_id=%s | profile_id=%s | filename=%s",
        conversation_id,
        profile.id,
        filename,
    )

    temp_path = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as temp_file:
            content = await file.read()
            temp_file.write(content)
            temp_path = temp_file.name

        if not content:
            raise HTTPException(status_code=400, detail="Empty file uploaded.")

        import pymupdf4llm

        try:
            markdown_text = await asyncio.to_thread(
                pymupdf4llm.to_markdown, temp_path
            )
            logger.info(
                "CHAT_UPLOAD_PDF_CONVERTED | len=%d",
                len(markdown_text),
            )
        except Exception as exc:
            logger.error("CHAT_UPLOAD_PDF_CONVERT_FAILED | error=%s", exc, exc_info=True)
            raise HTTPException(
                status_code=422,
                detail=f"Unable to convert PDF to Markdown: {exc}",
            )

        try:
            extracted = await extract_fields_from_pdf_markdown(markdown_text)
            total_keys = sum(len(v) for v in extracted.values())
            logger.info(
                "CHAT_UPLOAD_PDF_EXTRACTED | categories=%d | total_keys=%d",
                len(extracted),
                total_keys,
            )
        except Exception as exc:
            logger.error("CHAT_UPLOAD_PDF_EXTRACTION_FAILED | error=%s", exc, exc_info=True)
            raise HTTPException(
                status_code=422,
                detail=f"Unable to extract fields from PDF: {exc}",
            )

        missing = _validator.validate_extracted_fields(extracted)
        missing_count = sum(len(v) for v in missing.values())
        logger.info(
            "CHAT_UPLOAD_PDF_VALIDATED | missing_categories=%d | missing_keys=%d",
            len(missing),
            missing_count,
        )

        attr_creates = flatten_for_attributes(extracted)
        if attr_creates:
            await add_attributes_to_profile(db, profile.id, attr_creates)
            await db.commit()
            logger.info(
                "CHAT_UPLOAD_PDF_ATTRS_SAVED | count=%d",
                len(attr_creates),
            )

        user_msg_content = f"Uploaded PDF: {filename}"
        await svc_create_message(
            db,
            AssistantMessageCreate(
                conversation_id=conversation_id,
                role=MessageRole.USER,
                content=user_msg_content,
                message_metadata={
                    "type": "pdf_upload",
                    "file_name": filename,
                },
            ),
        )

        db_messages = await svc_list_messages(db, conversation_id)
        history = []
        for m in db_messages:
            if m.role == MessageRole.ASSISTANT and m.message_metadata and m.message_metadata.get("raw_content"):
                history.append({"role": m.role, "content": m.message_metadata["raw_content"]})
            else:
                history.append({"role": m.role, "content": m.content or ""})

        current_category = determine_current_category(missing)

        logger.info(
            "CHAT_UPLOAD_PDF_LLM_INPUT | collected_categories=%d | collected_keys=%d | missing_categories=%d",
            len(extracted),
            sum(len(v) for v in extracted.values()),
            len(missing),
        )
        assistant_text = await generate_pdf_upload_response(
            filename=filename,
            collected=extracted,
            missing=missing,
            current_category=current_category,
            history=history,
        )

        assistant_msg_raw = await svc_create_message(
            db,
            AssistantMessageCreate(
                conversation_id=conversation_id,
                role=MessageRole.ASSISTANT,
                content=assistant_text,
                model=settings.OPENAI_MODEL,
                message_metadata={"raw_content": assistant_text},
            ),
        )
        assistant_msg = AssistantMessageResponse.model_validate(assistant_msg_raw)

        profile_status = profile.status
        updated_attrs = []

        logger.info(
            "CHAT_UPLOAD_PDF_DONE | conversation_id=%s | profile_id=%s | new_attrs=%d | status=%s",
            conversation_id,
            profile.id,
            len(updated_attrs),
            profile_status,
        )

        return ChatResponse(
            assistant_message=assistant_msg,
            updated_attributes=updated_attrs,
            current_category=current_category,
            missing_fields=missing,
            profile_status=profile_status,
            profile_id=profile.id,
        )

    finally:
        if temp_path and os.path.exists(temp_path):
            os.unlink(temp_path)


async def close_chat(db: AsyncSession, conversation_id: UUID) -> ChatResponse:
    try:
        farewell_msg, profile_id, profile_status, collected = (
            await close_conversation_service(db, conversation_id)
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))

    logger.info(
        "CHAT_CLOSED_MANUAL | conversation_id=%s | profile_id=%s | status=%s",
        conversation_id,
        profile_id,
        profile_status,
    )

    return ChatResponse(
        assistant_message=farewell_msg,
        updated_attributes=[],
        current_category="complete",
        missing_fields=collected,
        profile_status=profile_status,
        profile_id=profile_id,
    )
