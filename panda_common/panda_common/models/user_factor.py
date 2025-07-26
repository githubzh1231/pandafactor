
from datetime import datetime
from typing import Dict, Optional



class UserFactor:
    
    def __init__(
        self,
        user_id: str,
        name: str,
        factor_name: str,
        type: str,
        is_persistent: bool,
        code: str,
        status: int,
        progress: int,
        describe: str = "",
        params: Optional[Dict] = None,
        gmt_created: Optional[datetime] = None,
        gmt_updated: Optional[datetime] = None
    ):
        self.user_id = user_id
        self.name = name
        self.factor_name = factor_name
        self.type = type
        self.is_persistent = is_persistent
        self.code = code
        self.status = status
        self.progress = progress
        self.describe = describe
        self.params = params or {}
        self.gmt_created = gmt_created or datetime.now()
        self.gmt_updated = gmt_updated or datetime.now()

    def to_dict(self) -> Dict:
        return {
            "user_id": self.user_id,
            "name": self.name,
            "factor_name": self.factor_name,
            "type": self.type,
            "is_persistent": self.is_persistent,
            "code": self.code,
            "status": self.status,
            "progress": self.progress,
            "describe": self.describe,
            "params": self.params,
            "gmt_created": self.gmt_created,
            "gmt_updated": self.gmt_updated
        }

    @classmethod
    def from_dict(cls, data: Dict) -> "UserFactor":
        return cls(
            user_id=data["user_id"],
            name=data["name"],
            factor_name=data["factor_name"],
            type=data["type"],
            is_persistent=data["is_persistent"],
            code=data["code"],
            status=data["status"],
            describe=data.get("describe", ""),
            params=data.get("params", {}),
            gmt_created=data.get("gmt_created"),
            gmt_updated=data.get("gmt_updated")
        )
