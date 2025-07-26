from panda_common.handlers.database_handler import DatabaseHandler
from panda_common.config import config
from panda_common.logger_config import logger
from panda_llm.models.chat import *
from bson import ObjectId


class MongoDBService:
    def __init__(self):
        self.db_handler = DatabaseHandler(config)
        self.collection = self.db_handler.get_mongo_collection("panda","chat_sessions")
        self.logger = logger

    async def create_chat_session(self, session: ChatSession) -> str:
        """创建新的聊天会话"""
        try:
            result = self.collection.insert_one(session.dict())
            return str(result.inserted_id)
        except Exception as e:
            self.logger.error(f"创建会话失败: {str(e)}")
            raise

    async def get_chat_session(self, session_id: str) -> Optional[ChatSession]:
        """获取聊天会话"""
        try:
            # 尝试将 session_id 转换为 ObjectId
            try:
                query = {"_id": ObjectId(session_id)}
            except:
                # 如果不是有效的 ObjectId，则使用原始字符串
                query = {"_id": session_id}
                
            session = self.collection.find_one(query)
            if session:
                return ChatSession(**session)
            return None
        except Exception as e:
            self.logger.error(f"获取会话失败: {str(e)}")
            raise

    async def update_chat_session(self, session_id: str, session: ChatSession):
        """更新聊天会话"""
        try:
            # 尝试将 session_id 转换为 ObjectId
            try:
                query = {"_id": ObjectId(session_id)}
            except:
                # 如果不是有效的 ObjectId，则使用原始字符串
                query = {"_id": session_id}
                
            self.collection.update_one(
                query,
                {"$set": session.dict()}
            )
        except Exception as e:
            self.logger.error(f"更新会话失败: {str(e)}")
            raise

    async def delete_chat_session(self, session_id: str):
        """删除聊天会话"""
        try:
            # 尝试将 session_id 转换为 ObjectId
            try:
                query = {"_id": ObjectId(session_id)}
            except:
                # 如果不是有效的 ObjectId，则使用原始字符串
                query = {"_id": session_id}
                
            self.collection.delete_one(query)
        except Exception as e:
            self.logger.error(f"删除会话失败: {str(e)}")
            raise

    async def get_user_sessions(self, user_id: str) -> List[ChatSession]:
        """获取用户的所有会话"""
        try:
            sessions = list(self.collection.find({"user_id": user_id}))
            return [ChatSession(**session) for session in sessions]
        except Exception as e:
            self.logger.error(f"获取用户会话失败: {str(e)}")
            raise