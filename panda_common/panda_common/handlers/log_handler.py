import logging
import uuid
from datetime import datetime
from typing import Dict, Any, Optional, List
from panda_common.handlers.database_handler import DatabaseHandler
from panda_common.config import config
import threading
import time
import os

class LogBatchManager:
    """Log batch manager that caches logs and periodically writes them to the database"""
    
    _instance = None
    _lock = threading.Lock()
    
    @classmethod
    def get_instance(cls):
        """Get singleton instance"""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = LogBatchManager()
        return cls._instance
    
    def __init__(self):
        """Initialize batch manager"""
        self.log_buffer = {}  # Log cache grouped by task_id
        self.buffer_lock = threading.Lock()
        self.db_handler = DatabaseHandler(config)
        self.flush_interval = 5  # Flush interval (seconds)
        self.max_buffer_size = 50  # Maximum number of cached logs per task
        
        # Start background thread for periodic log flushing
        self.stop_flag = False
        self.flush_thread = threading.Thread(target=self._flush_loop)
        self.flush_thread.daemon = True
        self.flush_thread.start()
    
    def add_log(self, task_id: str, log_entry: Dict[str, Any]):
        """Add log to cache"""
        with self.buffer_lock:
            if task_id not in self.log_buffer:
                self.log_buffer[task_id] = []
            
            self.log_buffer[task_id].append(log_entry)
            
            # If cache reaches threshold, flush immediately
            if len(self.log_buffer[task_id]) >= self.max_buffer_size:
                self._flush_task_logs(task_id)
    
    def _flush_loop(self):
        """Background thread for periodic log flushing"""
        while not self.stop_flag:
            time.sleep(self.flush_interval)
            self.flush_all()
    
    def _flush_task_logs(self, task_id: str):
        """Flush logs of specified task to database"""
        logs_to_save = []
        with self.buffer_lock:
            if task_id in self.log_buffer and self.log_buffer[task_id]:
                logs_to_save = self.log_buffer[task_id]
                self.log_buffer[task_id] = []
        
        if logs_to_save:
            try:
                for log in logs_to_save:
                    # Build log record
                    log_record = {
                        "log_id": str(uuid.uuid4()),
                        "task_id": log["task_id"],
                        "factor_id": log["factor_id"],
                        "message": log["message"],
                        "level": log["level"],
                        "timestamp": log["timestamp"],
                        "stage": log.get("stage", "default"),
                        "details": log.get("details"),
                        "created_at": datetime.now().isoformat(),
                        "updated_at": datetime.now().isoformat()
                    }
                    
                    # Direct insert into database
                    self.db_handler.mongo_insert("panda", "factor_analysis_stage_logs", log_record)
                
                # Update task status
                if len(logs_to_save) > 0:
                    latest_log = logs_to_save[-1]
                    self.db_handler.mongo_update(
                        "panda",
                        "tasks",
                        {"task_id": latest_log["task_id"]},
                        {
                            "current_stage": latest_log.get("stage", "unknown"),
                            "last_log_message": latest_log["message"],
                            "last_log_time": latest_log["timestamp"],
                            "last_log_level": latest_log["level"],
                            "updated_at": datetime.now().isoformat()
                        }
                    )
            except Exception as e:
                print(f"Error saving batch logs: {e}")
    
    def flush_all(self):
        """Flush logs of all tasks"""
        with self.buffer_lock:
            task_ids = list(self.log_buffer.keys())
        
        for task_id in task_ids:
            self._flush_task_logs(task_id)
    
    def shutdown(self):
        """Shutdown batch manager"""
        self.stop_flag = True
        if self.flush_thread.is_alive():
            self.flush_thread.join(timeout=10)
        self.flush_all()  # Ensure all logs are saved

class FactorAnalysisLogHandler(logging.Handler):
    """Factor analysis log handler that saves logs to MongoDB"""

    def __init__(self, task_id: str, factor_id: str, level=logging.INFO):
        """
        Initialize log handler
        
        Parameters:
        - task_id: Task ID
        - factor_id: Factor ID
        - level: Log level
        """
        super().__init__(level)
        self.task_id = task_id
        self.factor_id = factor_id
        self.batch_manager = LogBatchManager.get_instance()
        
        # Create formatter
        self.formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        
    def emit(self, record):
        """Record log to MongoDB"""
        try:
            # Get information from extra
            stage = getattr(record, 'stage', 'default')
            details = getattr(record, 'details', {})
            
            # Record main log
            log_entry = {
                "log_id": str(uuid.uuid4()),
                "task_id": self.task_id,
                "factor_id": self.factor_id,
                "level": record.levelname,
                "message": self.format(record),
                "timestamp": datetime.now().isoformat(),
                "stage": stage
            }
            
            # Add to batch manager
            self.batch_manager.add_log(self.task_id, log_entry)
            
            # If there are details, create separate debug logs for each field
            if details:
                for key, value in details.items():
                    debug_entry = {
                        "log_id": str(uuid.uuid4()),
                        "task_id": self.task_id,
                        "factor_id": self.factor_id,
                        "level": "DEBUG",
                        "message": f"{key}: {value}",
                        "timestamp": datetime.now().isoformat(),
                        "stage": stage
                    }
                    self.batch_manager.add_log(self.task_id, debug_entry)
            
            # For real-time response, important logs are written immediately
            if record.levelname in ("ERROR", "CRITICAL", "WARNING"):
                self.batch_manager.flush_all()
                
        except Exception as e:
            # Avoid application crash due to log processing exceptions
            print(f"Error saving log to MongoDB: {e}")
            
def get_factor_logger(task_id: str, factor_id: str) -> logging.Logger:
    """
    Get dedicated logger for factor analysis
    
    Parameters:
    - task_id: Task ID
    - factor_id: Factor ID
    
    Returns:
    - logging.Logger: Configured logger
    """
    # Create logger
    logger = logging.getLogger(f"factor_analysis_{task_id}")
    logger.setLevel(logging.DEBUG)  # Set log level to DEBUG
    
    # Don't add handlers if they already exist
    if logger.handlers:
        return logger
        
    # Create console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.DEBUG)  # Console only shows INFO and above levels
    console_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)
    
    # Create MongoDB handler
    mongo_handler = FactorAnalysisLogHandler(
        task_id=task_id,
        factor_id=factor_id
    )
    mongo_handler.setLevel(logging.DEBUG)  # MongoDB records all levels
    mongo_formatter = logging.Formatter('%(message)s')
    mongo_handler.setFormatter(mongo_formatter)
    logger.addHandler(mongo_handler)
    
    return logger