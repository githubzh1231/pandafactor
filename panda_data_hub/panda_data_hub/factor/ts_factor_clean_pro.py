import traceback
from abc import ABC
from datetime import datetime

import pandas as pd
from pymongo import UpdateOne

from panda_common.handlers.database_handler import DatabaseHandler
import tushare as ts

from panda_common.logger_config import logger
from panda_data_hub.utils.mongo_utils import ensure_collection_and_indexes
from panda_data_hub.utils.ts_utils import get_tushare_suffix


class TSFactorCleaner(ABC):

    def __init__(self, config):
        self.config = config
        self.db_handler = DatabaseHandler(config)
        try:
            ts.set_token(config['TS_TOKEN'])
            self.pro = ts.pro_api()
        except Exception as e:
            error_msg = f"Failed to initialize tushare: {str(e)}\nStack trace:\n{traceback.format_exc()}"
            logger.error(error_msg)
            raise

    def clean_daily_factor(self):
        try:
            date = datetime.now().strftime('%Y%m%d')
            query = {"date": date}
            records = self.db_handler.mongo_find(self.config["MONGO_DB"], 'stock_market', query)
            if records is None or len(records) == 0:
                logger.info(f"records none for {date}")
                return

            data = pd.DataFrame(list(records))
            data = data[['date', 'symbol', 'open','high','low','close','volume']]
            data['ts_code'] = data['symbol'].apply(get_tushare_suffix)

            logger.info("正在获取市值和换手率数据数据......")
            factor_data = self.pro.query('daily_basic', trade_date=date,fields=['ts_code','turnover_rate','total_mv'])
            temp_data = data.merge(factor_data[['ts_code','turnover_rate','total_mv']], on='ts_code', how='left')
            temp_data = temp_data.rename(columns={'total_mv': 'market_cap'})
            temp_data = temp_data.rename(columns={'turnover_rate': 'turnover'})
            logger.info("正在获取成交额数据......")
            price_data = self.pro.query("daily", trade_date=date, fields=['ts_code', 'amount'])
            result_data = temp_data.merge(price_data[['ts_code', 'amount']], on='ts_code', how='left')
            result_data = result_data.drop(columns=['ts_code'])
            # tushare的成交额是以千元为单位的
            result_data['amount'] = result_data['amount'] * 1000
            result_data['market_cap'] = result_data['market_cap'] * 10000
            desired_order = ['date', 'symbol', 'open', 'high', 'low', 'close', 'volume', 'market_cap', 'turnover','amount']
            result_data = result_data[desired_order]
            ensure_collection_and_indexes(table_name='factor_base')
            upsert_operations = []
            for record in result_data.to_dict('records'):
                upsert_operations.append(UpdateOne(
                    {'date': record['date'], 'symbol': record['symbol']},
                    {'$set': record},
                    upsert=True
                ))
            if upsert_operations:
                self.db_handler.mongo_client[self.config["MONGO_DB"]]['factor_base'].bulk_write(
                    upsert_operations)
                logger.info(f"Successfully upserted factor data for date: {date}")


        except Exception as e:
            error_msg = f"Failed to process market data for quarter : {str(e)}\nStack trace:\n{traceback.format_exc()}"
            logger.error(error_msg)
            raise