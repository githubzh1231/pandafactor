from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
import datetime
from panda_common.config import config, logger
from panda_common.handlers.database_handler import DatabaseHandler
from panda_data_hub.factor.rq_factor_clean_pro import RQFactorCleaner
from panda_data_hub.factor.ts_factor_clean_pro import TSFactorCleaner
# from panda_data_hub.factor.xt_factor_clean_pro import XTFactorCleaner


class FactorCleanerScheduler():

    def __init__(self):
        self.config = config

        # 初始化数据库连接
        self.db_handler = DatabaseHandler(self.config)
        # 初始化调度器
        self.scheduler = BackgroundScheduler()
        self.scheduler.start()

    def _process_factor(self):
        logger.info(f"Processing data ")
        try:
            data_source = config['DATAHUBSOURCE']
            if data_source == 'ricequant':
                # 清洗因子数据
                factor_cleaner = RQFactorCleaner(self.config)
                factor_cleaner.clean_daily_factor()
            elif data_source == 'tushare':
                # 清洗因子数据
                factor_cleaner = TSFactorCleaner(self.config)
                factor_cleaner.clean_daily_factor()
            # if data_source == 'xuntou':
            #     factor_cleaner = XTFactorCleaner(self.config)
            #     factor_cleaner.clean_daily_factor()

        except Exception as e:
            logger.error(f"Error _process_data : {str(e)}")

    def schedule_data(self):
        time = self.config["FACTOR_UPDATE_TIME"]
        hour, minute = time.split(":")
        trigger = CronTrigger(
            minute=minute,
            hour=hour,
            day='*',
            month='*',
            day_of_week='*'
        )

        # 添加定时任务
        self.scheduler.add_job(
            self._process_factor,
            trigger=trigger,
            id=f"data_{datetime.datetime.now().strftime('%Y%m%d')}",
            replace_existing=True
        )
        # self._process_factor()
        logger.info(f"Scheduled Data")

    def stop(self):
        """停止调度器"""
        self.scheduler.shutdown()


















