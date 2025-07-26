from pydantic import BaseModel


class ConfigRequest(BaseModel):
    # Mongo相关配置
    mongo_uri: str
    username: str
    password: str
    auth_db: str
    db_name:str
    # 数据源相关配置
    data_source: str
    m_user_name:str
    m_password:str
    admin_token:str
    # 数据清洗时间
    stock_clean_time:str
    factor_clean_time:str