from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from loguru import logger

from packages.interfaces.dataset_repository import DatasetRepository


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Manage the application lifecycle."""

    logger.info("Starting Athena AI...")
    repository: DatasetRepository = app.state.dataset_repository
    repository.initialize()

    try:
        yield
    finally:
        repository.close()

        logger.info("Stopping Athena AI...")
