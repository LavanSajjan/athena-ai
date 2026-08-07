from pydantic import BaseModel


class RootResponse(BaseModel):
    name: str
    description: str
    version: str


class HealthResponse(BaseModel):
    status: str


class VersionResponse(BaseModel):
    version: str