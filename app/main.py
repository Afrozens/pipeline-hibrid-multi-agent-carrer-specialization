import logging
import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

from app.core.config import get_settings
from app.generation.graph import build_profile_graph, set_profile_graph_instance
from app.router import api_router

settings = get_settings()
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    if settings.LANGCHAIN_API_KEY:
        os.environ["LANGCHAIN_API_KEY"] = settings.LANGCHAIN_API_KEY
    if settings.LANGCHAIN_TRACING_V2:
        os.environ["LANGCHAIN_TRACING_V2"] = "true"
    if settings.LANGCHAIN_PROJECT:
        os.environ["LANGCHAIN_PROJECT"] = settings.LANGCHAIN_PROJECT
    if settings.LANGCHAIN_ENDPOINT:
        os.environ["LANGCHAIN_ENDPOINT"] = settings.LANGCHAIN_ENDPOINT

    logger.info(
        "LANGSMITH_STATUS | tracing=%s | project=%s | endpoint=%s | key_set=%s",
        settings.LANGCHAIN_TRACING_V2,
        settings.LANGCHAIN_PROJECT,
        settings.LANGCHAIN_ENDPOINT,
        bool(settings.LANGCHAIN_API_KEY),
    )

    async with AsyncPostgresSaver.from_conn_string(
        settings.langgraph_database_uri
    ) as checkpointer:
        await checkpointer.setup()
        graph = await build_profile_graph(checkpointer)
        set_profile_graph_instance(graph)
        app.state.langgraph_checkpointer = checkpointer
        logger.info("LANGGRAPH_PIPELINE_READY | uri=%s", settings.langgraph_database_uri)

        yield

        logger.info("LANGGRAPH_CHECKPOINTER_CLOSED")


app = FastAPI(
    title=settings.APP_NAME,
    lifespan=lifespan,
)

app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.FRONTEND_HOST] if hasattr(settings, "FRONTEND_HOST") and settings.FRONTEND_HOST else ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
