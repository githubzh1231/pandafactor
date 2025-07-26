import logging
import sys
from datetime import datetime


class Logger:
    """Utility class for standardized logging"""

    _instance = None
    _logger = None

    @classmethod
    def get_logger(cls):
        """Get singleton logger instance"""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def __init__(self):
        """Initialize logger with standard configuration"""
        if Logger._logger is not None:
            raise Exception("Logger is a singleton!")

        # Create logger
        logger = logging.getLogger('panda_factor')
        logger.setLevel(logging.DEBUG)

        # Create console handler
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.INFO)

        # Create file handler
        file_handler = logging.FileHandler(
            f'logs/panda_factor_{datetime.now().strftime("%Y%m%d")}.log'
        )
        file_handler.setLevel(logging.DEBUG)

        # Create formatters
        console_formatter = logging.Formatter(
            '%(asctime)s - %(levelname)s - %(message)s'
        )
        file_formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s'
        )

        # Add formatters to handlers
        console_handler.setFormatter(console_formatter)
        file_handler.setFormatter(file_formatter)

        # Add handlers to logger
        logger.addHandler(console_handler)
        logger.addHandler(file_handler)

        Logger._logger = logger

    def info(self, message):
        """Log info message"""
        Logger._logger.info(message)

    def error(self, message, exc_info=True):
        """Log error message with exception info"""
        Logger._logger.error(message, exc_info=exc_info)

    def debug(self, message):
        """Log debug message"""
        Logger._logger.debug(message)

    def warning(self, message):
        """Log warning message"""
        Logger._logger.warning(message)


# Global logger instance
logger = Logger.get_logger()