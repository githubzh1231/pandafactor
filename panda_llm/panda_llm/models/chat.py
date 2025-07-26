from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime

class Message(BaseModel):
    role: str  # user 或 assistant
    content: str
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())

class ChatSession(BaseModel):
    id: str
    user_id: str
    messages: List[Message] = Field(default_factory=list)
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.now().isoformat())

    class Config:
        schema_extra = {
            "example": {
                "user_id": "user123",
                "messages": [
                    {
                        "role": "user",
                        "content": "你好",
                        "timestamp": datetime.now().isoformat()
                    },
                    {
                        "role": "assistant",
                        "content": "你好！有什么我可以帮你的吗？",
                        "timestamp": datetime.now().isoformat()
                    }
                ],
                "created_at": datetime.now().isoformat(),
                "updated_at": datetime.now().isoformat()
            }
        }

class ChatRequest(BaseModel):
    user_id: str
    message: str
    session_id: Optional[str] = None

    class Config:
        schema_extra = {
            "example": {
                "user_id": "user123",
                "message": "你好",
                "session_id": "optional_session_id"
            }
        }

class ChatResponse(BaseModel):
    session_id: str
    message: str
    timestamp: str

    class Config:
        schema_extra = {
            "example": {
                "session_id": "session123",
                "message": "你好！有什么我可以帮你的吗？",
                "timestamp": datetime.now().isoformat()
            }
        } 