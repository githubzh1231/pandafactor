from pydantic import BaseModel
from typing import Optional, TypeVar, Generic, Any

T = TypeVar('T')

class ResultData(BaseModel, Generic[T]):
    code: str
    message: str
    data: Optional[T] = None

    @staticmethod
    def success(message: str = "success", data: Any = None) -> 'ResultData':
        return ResultData(
            code="200",
            message=message,
            data=data
        )

    @staticmethod
    def fail(code: str, message: str) -> 'ResultData':
        return ResultData(
            code=code,
            message=message,
            data=None
        )