import traceback
from abc import ABC

import pandas as pd
from pymongo import UpdateOne

from panda_common.handlers.database_handler import DatabaseHandler
from panda_common.logger_config import logger
from datetime import datetime

from panda_data_hub.utils.mongo_utils import ensure_collection_and_indexes
from panda_data_hub.utils.xt_utils import xt_is_trading_day, get_xt_suffix, xt_get_total_volume, \
    xt_get_amount, XTQuantManager


class XTFactorCleaner(ABC):
    def __init__(self, config):
        self.config = config
        self.db_handler = DatabaseHandler(config)
        try:
            XTQuantManager.get_instance(config)
            logger.info("XtQuant ready to use")
        except Exception as e:
            error_msg = f"Failed to initialize XtQuant: {str(e)}\nStack trace:\n{traceback.format_exc()}"
            logger.error(error_msg)
            raise

    def clean_daily_factor(self):
        date_str = datetime.now().strftime("%Y%m%d")
        if xt_is_trading_day(date_str):
            try:
                logger.info(f"开始清洗因子数据: {date_str}")
                self.clean_factor_data(date_str=date_str)
            except Exception as e:
                logger.error(f"{str(e)}")
                return 0
        else:
            logger.info(f"跳过非交易日: {date_str}")
            return

    def clean_factor_data(self, date_str):
        try:
            date = date_str.replace('-', '')
            query = {"date": date}
            records = self.db_handler.mongo_find(self.config["MONGO_DB"], "stock_market", query)
            if records is None or len(records) == 0:
                logger.info(f"records none for {date}")
                return
            data = pd.DataFrame(list(records))
            data = data[['date', 'symbol', 'open', 'high', 'low', 'close', 'volume']]
            # 获取计算换手率和市值必要的数据
            data['stock_code'] = data['symbol'].apply(get_xt_suffix)
            data['TotalVolume'] = data['stock_code'].apply(xt_get_total_volume)
            # 计算换手率和市值因子
            data['turnover'] = data['volume'] / data['TotalVolume']
            data['turnover'] = data['turnover'] * 100
            data['turnover'] = data['turnover'].round(4)
            data['market_cap'] = data['close'] * data['TotalVolume']
            # 获取成交额数据
            logger.info("正在获取历史成交额数据.......")
            data['amount'] = data['stock_code'].apply(lambda code: xt_get_amount(code, date))
            data = data.drop(columns=['TotalVolume', 'stock_code'])
            ensure_collection_and_indexes(table_name='factor_base')
            upsert_operations = []
            for record in data.to_dict('records'):
                upsert_operations.append(UpdateOne(
                    {'date': record['date'], 'symbol': record['symbol']},
                    {'$set': record},
                    upsert=True
                ))
            if upsert_operations:
                self.db_handler.mongo_client[self.config["MONGO_DB"]]['factor_base'].bulk_write(upsert_operations)
                logger.info(f"Successfully upserted factor data for date:{date}")
        except Exception as e:
            error_msg = f"Failed to process factor for quanter: {e}"
            logger.error(error_msg)
            raise
