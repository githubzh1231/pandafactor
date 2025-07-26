from datetime import datetime
from typing import List, Optional, AsyncGenerator
from panda_common.logger_config import logger
from panda_llm.services.mongodb import MongoDBService
from panda_llm.models.chat import ChatSession, Message
from panda_llm.services.llm_service import LLMService
import uuid


class ChatService:
    def __init__(self):
        self.mongodb = MongoDBService()
        self.logger = logger

    async def process_message(self, session_id: str, user_message: str, user_id: str) -> str:
        """处理用户消息并返回 AI 响应"""
        try:
            # 获取或创建会话
            session = await self.mongodb.get_chat_session(session_id)
            if not session:
                # 创建新会话时生成唯一 ID
                session = ChatSession(
                    id=str(uuid.uuid4()),
                    user_id=user_id,
                    messages=[],
                    created_at=datetime.now().isoformat(),
                    updated_at=datetime.now().isoformat()
                )
                await self.mongodb.create_chat_session(session)

            # 添加用户消息
            user_msg = Message(role="user", content=user_message)
            session.messages.append(user_msg)
            await self.mongodb.update_chat_session(session.id, session)

            # 调用 AI 服务
            llm = LLMService()
            ai_response = await llm.chat_completion(session.messages)

            # 添加 AI 响应
            ai_msg = Message(role="assistant", content=ai_response)
            session.messages.append(ai_msg)
            await self.mongodb.update_chat_session(session.id, session)

            return ai_response

        except Exception as e:
            self.logger.error(f"处理消息失败: {str(e)}")
            raise

    async def get_session_messages(self, session_id: str) -> List[Message]:
        """获取会话消息历史"""
        session = await self.mongodb.get_chat_session(session_id)
        return session.messages if session else []

    async def clear_session(self, session_id: str):
        """清空会话"""
        await self.mongodb.delete_chat_session(session_id)

    async def process_message_stream(self, user_id: str, message: str, session_id: Optional[str] = None) -> AsyncGenerator[str, None]:
        """处理用户消息并流式返回回复"""
        try:
            # 创建用户消息
            user_message = Message(
                role="user",
                content=message,
                timestamp=datetime.now().isoformat()
            )

            # 获取或创建会话
            if session_id:
                session = await self.mongodb.get_chat_session(session_id)
                if not session:
                    logger.error(f"会话不存在: {session_id}")
                    raise ValueError(f"会话不存在: {session_id}")
            else:
                session = ChatSession(
                    id=str(uuid.uuid4()),
                    user_id=user_id,
                    messages=[user_message],
                    created_at=datetime.now().isoformat(),
                    updated_at=datetime.now().isoformat()
                )
                session_id = await self.mongodb.create_chat_session(session)
                logger.info(f"创建新会话: {session_id}")

            # 更新会话
            session.messages.append(user_message)
            await self.mongodb.update_chat_session(session.id, session)

            # 准备历史消息
            messages = [{"role": msg.role, "content": msg.content} for msg in session.messages]

            # 调用 AI 服务
            llm = LLMService()
            full_response = ""
            async for chunk in llm.chat_completion_stream(messages):
                full_response += chunk
                yield chunk

            # 添加 AI 响应
            ai_msg = Message(role="assistant", content=full_response)
            session.messages.append(ai_msg)
            await self.mongodb.update_chat_session(session.id, session)

        except Exception as e:
            self.logger.error(f"处理消息失败: {str(e)}")
            raise

    async def get_user_sessions(self, user_id: str, limit: int = 10) -> List[ChatSession]:
        """获取用户的聊天会话列表"""
        try:
            sessions = await self.mongodb.get_user_sessions(user_id)
            return sessions[:limit]
        except Exception as e:
            self.logger.error(f"获取用户会话列表失败: {str(e)}")
            raise 