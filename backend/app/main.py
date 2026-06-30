"""FastAPI application entry point."""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from app.asyncio_compat import configure_asyncio_for_playwright

configure_asyncio_for_playwright()

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.config import APP_TITLE, APP_VERSION, CORS_ORIGINS
from app.database import BACKEND_DIR
from app.database import init_db
from app.routers.llm_usage import router as llm_usage_router
from app.routers.profiles import router as profiles_router
from app.routers.tasks import router as tasks_router
from app.schemas import HealthResponse, LLMProviderResponse
from app.services.llm_provider_config import list_llm_providers


def configure_application_logging() -> None:
    """Make backend application logs visible during local development."""

    logging.basicConfig(
        level=logging.INFO,
        format="%(levelname)s:     %(message)s",
    )
    logging.getLogger("app").setLevel(logging.INFO)


configure_application_logging()


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    """Initialize application resources at startup."""

    init_db()
    yield


app = FastAPI(
    title=APP_TITLE,
    version=APP_VERSION,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(profiles_router)
app.include_router(tasks_router)
app.include_router(llm_usage_router)
app.mount(
    "/screenshots",
    StaticFiles(directory=BACKEND_DIR / "screenshots"),
    name="screenshots",
)


@app.get("/health", response_model=HealthResponse, tags=["system"])
async def health_check() -> HealthResponse:
    """Return the API health status."""

    return HealthResponse(status="ok")


@app.get(
    "/llm/providers",
    response_model=list[LLMProviderResponse],
    tags=["system"],
)
async def llm_providers() -> list[dict[str, object]]:
    """Return selectable LLM providers and setup hints."""

    return list_llm_providers()
