from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class ApiKeySaveRequest(BaseModel):
    provider: str = Field(..., description="e.g. anthropic, openai, ollama")
    api_key: str = Field(..., min_length=1, description="The raw API key")


class ApiKeyStatusResponse(BaseModel):
    id: int
    provider: str
    env_var_name: str
    is_configured: bool
    status: str              # 'configured' or 'missing'
    last_verified: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class ApiKeyVerifyResponse(BaseModel):
    provider: str
    status: str
    message: str