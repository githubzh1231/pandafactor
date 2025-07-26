import aiohttp
import json
from typing import List, Dict, AsyncGenerator
from panda_llm.panda_llm.config import OLLAMA_BASE_URL, OLLAMA_MODEL
from panda_common.logger_config import logger

class LLMService:
    def __init__(self):
        self.logger = logger
        self.base_url = OLLAMA_BASE_URL
        self.model = OLLAMA_MODEL
        self.session = None

    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()

    async def chat_completion(self, messages: List[Dict]) -> str:
        """调用本地 DeepSeek 服务"""
        try:
            url = f"{self.base_url}/api/chat"
            payload = {
                "model": self.model,
                "messages": messages
            }

            async with self.session.post(url, json=payload) as response:
                if response.status != 200:
                    error_text = await response.text()
                    self.logger.error(f"DeepSeek API 调用失败: {error_text}")
                    raise ValueError(f"AI 服务调用失败: {error_text}")

                result = await response.json()
                return result.get("message", {}).get("content", "")

        except Exception as e:
            self.logger.error(f"AI 服务调用失败: {str(e)}")
            raise ValueError("AI 服务暂时不可用，请稍后再试")

    async def chat_completion_stream(self, messages: List[Dict]) -> AsyncGenerator[str, None]:
        """流式调用本地 DeepSeek 服务"""
        try:
            url = f"{self.base_url}/api/chat"
            payload = {
                "model": self.model,
                "messages": messages,
                "stream": True
            }

            async with self.session.post(url, json=payload) as response:
                if response.status != 200:
                    error_text = await response.text()
                    self.logger.error(f"DeepSeek API 调用失败: {error_text}")
                    raise ValueError(f"AI 服务调用失败: {error_text}")

                async for line in response.content:
                    if line:
                        try:
                            data = json.loads(line)
                            if "message" in data and "content" in data["message"]:
                                yield data["message"]["content"]
                        except json.JSONDecodeError:
                            continue

        except Exception as e:
            self.logger.error(f"AI 服务调用失败: {str(e)}")
            raise ValueError("AI 服务暂时不可用，请稍后再试") 