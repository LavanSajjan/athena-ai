from contextlib import asynccontextmanager

from fastapi import FastAPI
from loguru import logger


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting Athena AI...")

    yield

    logger.info("Stopping Athena AI...")