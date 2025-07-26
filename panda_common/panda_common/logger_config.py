import logging
import os
import sys
import inspect
from datetime import datetime
from functools import wraps

# TODO Read log level from config file
# Create log directory
log_dir = "logs"
if not os.path.exists(log_dir):
    os.makedirs(log_dir)

# Create log filenames (using current date)
current_date = datetime.now().strftime("%Y%m%d")
log_file = os.path.join(log_dir, f"panda_info_{current_date}.log")
error_log_file = os.path.join(log_dir, f"panda_error_{current_date}.log")

# Configure log format
formatter = logging.Formatter(
    '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

# Create console handler
console_handler = logging.StreamHandler()
console_handler.setFormatter(formatter)

# Create file handler
file_handler = logging.FileHandler(log_file)
file_handler.setFormatter(formatter)

# Create error log file handler (only records ERROR level and above)
error_file_handler = logging.FileHandler(error_log_file)
error_file_handler.setFormatter(formatter)
error_file_handler.setLevel(logging.ERROR)

# Configure root logger
root_logger = logging.getLogger()
root_logger.setLevel(logging.INFO)
root_logger.addHandler(console_handler)
root_logger.addHandler(file_handler)
root_logger.addHandler(error_file_handler)

def get_logger(module_name):
    """
    Get logger for specified module
    
    Args:
        module_name: Module name, typically use __name__
        
    Returns:
        Logger: Configured logger instance
    """
    logger = logging.getLogger(module_name)
    # TODO Read log level from config file
    logger.setLevel(logging.INFO)
    return logger

# Global cache for created loggers to avoid duplicates
_module_loggers = {}

class LoggerInjector:
    @staticmethod
    def _get_caller_module_name():
        """Get the caller's module name"""
        frame = inspect.currentframe()
        if frame is None:
            return "__unknown__"
            
        # Get two levels up call frame (skip get_logger and current method)
        caller_frame = None
        try:
            # Need deeper frame level since this is accessed as property
            if frame.f_back is not None and frame.f_back.f_back is not None:
                caller_frame = frame.f_back.f_back
            module = inspect.getmodule(caller_frame)
            return module.__name__ if module else "__main__"
        except (AttributeError, TypeError):
            return "__unknown__"
        finally:
            # Clean up references to prevent memory leaks
            del frame
            if caller_frame:
                del caller_frame
    
    @classmethod
    def get_logger(cls):
        """Get logger for the module calling this method"""
        module_name = cls._get_caller_module_name()
        if module_name not in _module_loggers:
            _module_loggers[module_name] = get_logger(module_name)
        return _module_loggers[module_name]

# Module-level logger that forwards all calls to the appropriate module logger
class Logger:
    """
    A proxy class that forwards all logging methods to the appropriate module logger.
    This allows using 'logger.info()' directly without instantiation.
    """
    def debug(self, msg, *args, **kwargs):
        return LoggerInjector.get_logger().debug(msg, *args, **kwargs)
        
    def info(self, msg, *args, **kwargs):
        return LoggerInjector.get_logger().info(msg, *args, **kwargs)
        
    def warning(self, msg, *args, **kwargs):
        return LoggerInjector.get_logger().warning(msg, *args, **kwargs)
        
    def error(self, msg, *args, **kwargs):
        return LoggerInjector.get_logger().error(msg, *args, **kwargs)
        
    def critical(self, msg, *args, **kwargs):
        return LoggerInjector.get_logger().critical(msg, *args, **kwargs)
        
    def exception(self, msg, *args, **kwargs):
        return LoggerInjector.get_logger().exception(msg, *args, **kwargs)
        
    def log(self, level, msg, *args, **kwargs):
        return LoggerInjector.get_logger().log(level, msg, *args, **kwargs)
    
    # Additional logger methods
    def isEnabledFor(self, level):
        return LoggerInjector.get_logger().isEnabledFor(level)
    
    def getEffectiveLevel(self):
        return LoggerInjector.get_logger().getEffectiveLevel()
    
    def setLevel(self, level):
        return LoggerInjector.get_logger().setLevel(level)

# Create a single instance to be imported elsewhere
logger = Logger()