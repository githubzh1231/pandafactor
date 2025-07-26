import traceback
from abc import ABC
from concurrent.futures import ThreadPoolExecutor

from pymongo import UpdateOne
from tqdm import tqdm

from panda_common.handlers.database_handler import DatabaseHandler
# from xtquant import xtdata
# from xtquant import xtdatacenter as xtdc
from panda_common.logger_config import logger
import pandas as pd
from datetime import datetime

from panda_data_hub.utils.mongo_utils import ensure_collection_and_indexes
from panda_data_hub.utils.xt_utils import get_xt_suffix, xt_get_amount, XTQuantManager

'''
因为迅投无法获取历史的市值和换手率，因此迅投数据源的stock_market表不包含market_cap turnover这两个字段
'''
class FactorCleanerXTProService(ABC):
    def __init__(self,config):
        self.config = config
        self.db_handler = DatabaseHandler(config)
        self.progress_callback = None
        try:
            XTQuantManager.get_instance(config)
            logger.info("XtQuant ready to use")
        except Exception as e:
            error_msg = f"Failed to initialize XtQuant: {str(e)}\nStack trace:\n{traceback.format_exc()}"
            logger.error(error_msg)
            raise
    def set_progress_callback(self, callback):
        '''进度条实现'''
        self.progress_callback = callback

    def factor_history_clean(self,start_date,end_date):
        logger.info("Starting XTData cleaning for XTQuant")

        date_range = pd.date_range(start=start_date, end=end_date, freq='D')
        trading_days = []
        for date in date_range:
            date_str = datetime.strftime(date, "%Y-%m-%d")
            trading_days.append(date_str)
        logger.info(f"找到 {len(trading_days)} 个交易日需要处理")
        total_days = len(trading_days)
        progress_days = 0
        with tqdm(total=total_days,desc = "Processing TradingDays") as pbar:
            batch_size = 5
            for i in range(0,total_days,batch_size):
                batch_days = trading_days[i:i+batch_size]
                with ThreadPoolExecutor(max_workers=8) as executor:
                    futures = []
                    for date in batch_days:
                        futures.append(
                            executor.submit(
                                self.factor_daily_clean,
                                date_str = date,
                                pbar = pbar,
                            ))
                    for future in futures:
                        try:
                            future.result()
                            progress_days += 1
                            progress = int((progress_days/total_days)*100)
                            # 更新进度
                            if self.progress_callback:
                                self.progress_callback(progress)
                            pbar.update(1)
                        except Exception as e:
                            logger.error(e)
                            pbar.update(1)
        logger.info("所有交易日数据处理完成")

    def factor_daily_clean(self,date_str,pbar):
        try:
            date = date_str.replace('-','')
            query = {"date":date}
            records = self.db_handler.mongo_find(self.config["MONGO_DB"],"stock_market",query)
            if records is None or len(records) == 0:
                logger.info(f"records none for {date}")
                return
            data = pd.DataFrame(list(records))
            data = data[['date','symbol','open','high','low','close','volume']]
            # 获取成交额数据
            logger.info("正在获取历史成交额数据.......")
            data['ts_code'] = data['symbol'].apply(get_xt_suffix)
            data['amount'] = data['ts_code'].apply(lambda code: xt_get_amount(code, date))
            data = data.drop(columns=['ts_code'])
            ensure_collection_and_indexes(table_name='factor_base')
            upsert_operations = []
            for record in data.to_dict('records'):
                upsert_operations.append(UpdateOne(
                    {'date':record['date'],'symbol':record['symbol']},
                    {'$set':record},
                    upsert=True
                ))
            if upsert_operations:
                self.db_handler.mongo_client[self.config["MONGO_DB"]]['factor_base'].bulk_write(upsert_operations)
                logger.info(f"Successfully upserted factor data for date:{date}")

        except Exception as e:
            error_msg = f"Failed to process factor for quanter: {e}"
            logger.error(error_msg)
            raise



