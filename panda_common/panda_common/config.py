"""
配置模块，用于加载和管理配置信息
支持从配置文件和环境变量导入，环境变量优先级更高
"""
import os
import yaml
import logging
from pathlib import Path

# 获取logger
try:
    from panda_common.logger_config import logger
except ImportError:
    # 如果无法导入logger，创建一个基本的logger
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger("config")

# 初始化配置变量
config = None

def load_config():
    """加载配置文件，并从环境变量更新配置"""
    global config
    
    # 获取当前文件所在目录
    current_dir = os.path.dirname(os.path.abspath(__file__))
    config_path = os.path.join(current_dir, 'config.yaml')
    
    # 从配置文件加载基础配置
    try:
        with open(config_path, 'r',encoding='utf-8') as config_file:
            config = yaml.safe_load(config_file)
            logger.info(f"从配置文件加载配置: {config_path}")
    except Exception as e:
        error_msg = f"从 {config_path} 加载配置失败: {str(e)}"
        logger.error(error_msg)
        raise FileNotFoundError(error_msg)
    
    # 从环境变量更新配置
    for key in config.keys():
        env_value = os.environ.get(key)
        if env_value is not None:
            # 尝试将环境变量的值转换为与配置文件中相同的类型
            try:
                original_type = type(config[key])
                if original_type == bool:
                    config[key] = env_value.lower() in ('true', '1', 'yes')
                else:
                    config[key] = original_type(env_value)
                logger.info(f"从环境变量更新配置: {key}")
            except ValueError:
                logger.warning(f"环境变量 {key} 的值类型转换失败，保持原值")
                continue
    
    return config

def get_config():
    """
    获取配置对象，如果配置未加载则先加载配置
    
    Returns:
        dict: 配置信息字典
    """
    global config
    if config is None:
        config = load_config()
    return config

# 初始加载配置
try:
    config = load_config()
    logger.info(f"初始化配置成功: {config}")
except Exception as e:
    logger.error(f"初始化配置失败: {str(e)}")
    # 不在初始化时抛出异常，留到实际使用时再处理
