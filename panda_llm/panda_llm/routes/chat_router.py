from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional
import json

from panda_llm.services.chat_service import ChatService

router = APIRouter()
chat_service = ChatService()

class ChatRequest(BaseModel):
    user_id: str
    message: str
    session_id: Optional[str] = None

@router.post("/chat")
async def chat(request: ChatRequest):
    """处理聊天请求"""
    try:
        # 使用流式处理
        async def generate():
            try:
                # async for chunk in chat_service.process_message_stream(
                async for chunk in chat_service.process_message_stream(
                    request.user_id,
                    request.message,
                    request.session_id
                ):
                    yield f"data: {json.dumps({'content': chunk})}\n\n"
            except ValueError as e:
                yield f"data: {json.dumps({'error': str(e)})}\n\n"
            except Exception as e:
                yield f"data: {json.dumps({'error': '处理消息时发生错误'})}\n\n"
            finally:
                yield "data: [DONE]\n\n"

        return StreamingResponse(
            generate(),
            media_type="text/event-stream"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/chat/sessions")
async def get_sessions(user_id: str, limit: int = 10):
    """获取用户的聊天会话列表"""
    try:
        sessions = await chat_service.get_user_sessions(user_id, limit)
        return {"sessions": [session.dict() for session in sessions]}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) 