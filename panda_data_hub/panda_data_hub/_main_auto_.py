import signal
import sys
import time
from panda_common.logger_config import logger
from panda_data_hub.task.data_scheduler import DataScheduler
from panda_data_hub.task.factor_clean_scheduler import FactorCleanerScheduler


class SchedulerManager:
    def __init__(self):
        self.factor_scheduler = None
        self.data_scheduler = None

    def stop(self):
        if self.factor_scheduler:
            self.factor_scheduler.stop()
        if self.data_scheduler:
            self.data_scheduler.stop()

manager = SchedulerManager()

def signal_handler(signum, frame):
    logger.info("Received shutdown signal, stopping scheduler...")
    manager.stop()
    sys.exit(0)

if __name__ == "__main__":
    # Register signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    try:
        # 创建并启动调度器（股票）
        manager.data_scheduler = DataScheduler()
        manager.data_scheduler.schedule_data()
        # 创建并启动调度器（因子）
        manager.factor_scheduler = FactorCleanerScheduler()
        manager.factor_scheduler.schedule_data()

        logger.info("Factor scheduler started successfully")
        logger.info("Data scheduler started successfully")

        while True:
            time.sleep(1)

    except Exception as e:
        logger.error(f"Error starting scheduler: {str(e)}")
        sys.exit(1)