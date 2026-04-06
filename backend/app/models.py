from pydantic import BaseModel
from typing import Optional, List


class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = "default"
    stream: Optional[bool] = False


class ChatResponse(BaseModel):
    response: str
    session_id: str
    has_pending_changes: bool = False


class StreamChunk(BaseModel):
    type: str  # "token", "done", "error", "pending_preview"
    content: str
    session_id: str
    has_pending_changes: bool = False


class CommitRequest(BaseModel):
    session_id: Optional[str] = "default"


class RollbackRequest(BaseModel):
    session_id: Optional[str] = "default"


class SessionStatus(BaseModel):
    session_id: str
    has_pending_changes: bool = False
    pending_count: int = 0
