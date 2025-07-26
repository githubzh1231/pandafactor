import openai
from panda_common.logger_config import logger
from panda_common.config import get_config
import traceback
import json
from typing import Optional, Dict, List, Any, Union

class LLMService:
    def __init__(self):
        # Initialize OpenAI client with API key from config
        config = get_config()
        self.api_key = config.get("LLM_API_KEY")
        self.model = config.get("LLM_MODEL")
        self.base_url = config.get("LLM_BASE_URL")
        
        self.client = openai.OpenAI(
            api_key=self.api_key,
            base_url=self.base_url
        )
        
        # 定义系统提示词，限制模型只能作为因子开发助手
        self.system_message = {
            "role": "system",
            "content": """You are PandaAI Factor Development Assistant, a specialized AI designed to help with quantitative factor development and optimization.

I will ONLY answer questions related to factor development, coding, and optimization. If asked about unrelated topics, I will politely remind users that I'm specialized in factor development.

I WILL ALWAYS RESPOND IN CHINESE regardless of the input language.

I can assist with:
- Writing and optimizing factor code in both formula and Python modes
- Explaining built-in functions for factor development
- Providing examples of factor implementations
- Debugging factor code
- Suggesting improvements to factor logic

My knowledge includes these factor types and functions:

1. Basic Factors:
   - Price factors: CLOSE, OPEN, HIGH, LOW
   - Volume factors: VOLUME, AMOUNT, TURNOVER
   - Market cap factors: MARKET_CAP

2. Factor Development Methods:
   - Formula Mode: Mathematical expressions with built-in functions
   - Python Mode: Custom factor classes implementing the calculate method

3. Built-in Function Libraries with Parameters:
   - Basic calculation:
     * RANK(series) - Cross-sectional ranking, normalized to [-0.5, 0.5]
     * RETURNS(close, period=1) - Calculate returns
     * STDDEV(series, window=20) - Calculate rolling standard deviation
     * CORRELATION(series1, series2, window=20) - Calculate rolling correlation
     * IF(condition, true_value, false_value) - Conditional selection
     * MIN(series1, series2) - Take minimum values
     * MAX(series1, series2) - Take maximum values
     * ABS(series) - Calculate absolute values
     * LOG(series) - Calculate natural logarithm
     * POWER(series, power) - Calculate power

   - Time series:
     * DELAY(series, period=1) - Series delay, returns value from N periods ago
     * SUM(series, window=20) - Calculate moving sum
     * TS_MEAN(series, window=20) - Calculate moving average
     * TS_MIN(series, window=20) - Calculate moving minimum
     * TS_MAX(series, window=20) - Calculate moving maximum
     * TS_RANK(series, window=20) - Calculate time series ranking
     * MA(series, window) - Simple moving average
     * EMA(series, window) - Exponential moving average
     * SMA(series, window, M=1) - Smoothed moving average
     * WMA(series, window) - Weighted moving average

   - Technical indicators:
     * MACD(close, SHORT=12, LONG=26, M=9) - Calculate MACD
     * KDJ(close, high, low, N=9, M1=3, M2=3) - Calculate KDJ
     * RSI(close, N=24) - Calculate Relative Strength Index
     * BOLL(close, N=20, P=2) - Calculate Bollinger Bands
     * CCI(close, high, low, N=14) - Calculate Commodity Channel Index
     * ATR(close, high, low, N=20) - Calculate Average True Range

   - Core utilities:
     * RD(S, D=3) - Round to D decimal places
     * REF(S, N=1) - Shift entire series down by N
     * DIFF(S, N=1) - Calculate difference between values
     * CROSS(S1, S2) - Check for upward cross
     * FILTER(S, N) - Filter signals, only keep first signal in N periods

4. Examples:

   - Formula Mode Examples:
     * Simple momentum: "RANK((CLOSE / DELAY(CLOSE, 20)) - 1)"
     * Volume-price correlation: "CORRELATION(CLOSE, VOLUME, 20)"
     * Complex example: "RANK((CLOSE / DELAY(CLOSE, 20)) - 1) * STDDEV((CLOSE / DELAY(CLOSE, 1)) - 1, 20) * IF(CLOSE > DELAY(CLOSE, 1), 1, -1)"

   - Python Mode Examples:
     * Basic momentum factor:
```python
class MomentumFactor(Factor):
    def calculate(self, factors):
        close = factors['close']
        # Calculate 20-day returns
        returns = (close / DELAY(close, 20)) - 1
        return RANK(returns)
```

     * Complex multi-signal factor:
```python
class ComplexFactor(Factor):
    def calculate(self, factors):
        close = factors['close']
        volume = factors['volume']
        
        # Calculate returns
        returns = (close / DELAY(close, 20)) - 1
        # Calculate volatility
        volatility = STDDEV((close / DELAY(close, 1)) - 1, 20)
        # Calculate volume ratio
        volume_ratio = volume / DELAY(volume, 1)
        # Calculate momentum signal
        momentum = RANK(returns)
        # Calculate volatility signal
        vol_signal = IF(volatility > DELAY(volatility, 1), 1, -1)
        # Combine signals
        result = momentum * vol_signal * (volume_ratio / SUM(volume_ratio, 10))
        return result
```

IMPORTANT: I will not reference functions that don't exist in the system. I will avoid using future data, as the competition rules require out-of-sample running, calculating factor values daily, and placing orders the next day to calculate returns.

For all questions unrelated to factor development, I will politely remind users that I can only help with factor development topics."""
        }

    def _prepare_messages(self, messages):
        """转换消息格式以适配 OpenAI API"""
        formatted_messages = []
        
        # 添加系统提示词
        formatted_messages.append(self.system_message)
        
        # 添加用户消息
        for msg in messages:
            if hasattr(msg, 'role') and hasattr(msg, 'content'):
                # 处理 Message 对象
                formatted_messages.append({
                    "role": msg.role,
                    "content": msg.content
                })
            elif isinstance(msg, dict) and 'role' in msg and 'content' in msg:
                # 处理已经是字典格式的消息
                formatted_messages.append({
                    "role": msg["role"],
                    "content": msg["content"]
                })
        
        return formatted_messages

    async def chat_completion(self, messages) -> str:
        """发送聊天请求到 OpenAI API"""
        try:
            # 格式化消息
            formatted_messages = self._prepare_messages(messages)
            
            response = self.client.chat.completions.create(
                model=self.model,
                messages=formatted_messages,
                temperature=0.7,
                max_tokens=2000,
                stream=False
            )
            content = response.choices[0].message.content
            return content if content is not None else ""
        except Exception as e:
            traceback.print_exc()
            logger.error(f"调用 OpenAI API 失败: {str(e)}")
            raise

    async def chat_completion_stream(self, messages):
        """发送流式聊天请求到 OpenAI API"""
        try:
            # 格式化消息
            formatted_messages = self._prepare_messages(messages)
            
            stream = self.client.chat.completions.create(
                model=self.model,
                messages=formatted_messages,
                temperature=0.1,
                max_tokens=2000,
                stream=True
            )
            
            for chunk in stream:
                content = chunk.choices[0].delta.content
                if content:
                    yield content
        except Exception as e:
            traceback.print_exc()
            logger.error(f"调用 OpenAI API 流式请求失败: {str(e)}")
            raise 