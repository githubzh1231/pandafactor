from dataclasses import dataclass
from typing import Optional, Literal

@dataclass
class FactorParams:
    """因子参数数据类，用于封装因子计算所需的参数"""
    
    factor_id: str
    user_id: str
    name: str
    factor_name: str
    code: str
    code_type: str
    adjustment_cycle: str
    stock_pool: str
    factor_direction: str
    group_number: int
    include_st: bool
    extreme_value_processing: str
    
    @classmethod
    def from_record(cls, record: dict) -> 'FactorParams':
        """从记录字典创建FactorParams实例
        
        Args:
            record: 包含因子参数的字典
            
        Returns:
            FactorParams实例
        """
        return cls(
            factor_id=record["factorId"],
            user_id=record["userId"],
            name=record['factorDetails']["name"],
            factor_name=record['factorDetails']["factor_name"],
            code=record['factorDetails']["code"],
            code_type=record['factorDetails']["code_type"],
            adjustment_cycle=record['factorDetails']["adjustment_cycle"],
            stock_pool=record['factorDetails']["stock_pool"],
            factor_direction=record['factorDetails']["direction"],
            group_number=record['factorDetails']["group_number"],
            include_st=record['factorDetails']["include_st"],
            extreme_value_processing=record['factorDetails']["extreme_value_processing"]
        )
    
    def to_dict(self) -> dict:
        """将FactorParams实例转换为字典格式
        
        Returns:
            包含所有参数的字典
        """
        return {
            "factorId": self.factor_id,
            "userId": self.user_id,
            "factorDetails": {
                "name": self.name,
                "factor_name": self.factor_name,
                "code": self.code,
                "code_type": self.code_type,
                "adjustment_cycle": self.adjustment_cycle,
                "stock_pool": self.stock_pool,
                "direction": self.factor_direction,
                "group_number": self.group_number,
                "include_st": self.include_st,
                "extreme_value_processing": self.extreme_value_processing
            }
        } 