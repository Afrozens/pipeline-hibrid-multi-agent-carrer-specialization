import logging

from uuid import UUID
from langchain_core.tools import tool
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


def make_close_tool(db: AsyncSession, conversation_id: UUID):
    @tool
    async def close_conversation() -> str:
        """Mark the student profile as COMPLETE and close this assistant conversation.

        Call this ONLY after the student has explicitly confirmed that
        all collected profile information is correct and complete.
        The system will handle updating both statuses.
        """
        try:
            logger.info("CLOSE_CONVERSATION_WAITING")
        except Exception as ex:
            logger.info("CLOSE_CONVERSATION_ERROR | error=%s", str(ex))
            return "The conversation could not be closed at this time."
    return close_conversation
