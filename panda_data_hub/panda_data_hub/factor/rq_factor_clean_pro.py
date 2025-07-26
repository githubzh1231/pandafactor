from abc import ABC
from datetime import datetime

import pandas as pd
import rqdatac
import traceback
from pymongo import UpdateOne

from panda_common.handlers.database_handler import DatabaseHandler
from panda_common.logger_config import logger
from panda_data_hub.utils.mongo_utils import ensure_collection_and_indexes
from panda_data_hub.utils.rq_utils import get_ricequant_suffix


class RQFactorCleaner(ABC):

    def __init__(self,config):
        self.config = config
        self.db_handler = DatabaseHandler(config)

        try:
            rqdatac.init(config['MUSER'], config['MPASSWORD'])
            logger.info("RiceQuant initialized successfully")
            rqdatac.info()
        except Exception as e:
            error_msg = f"Failed to initialize RiceQuant: {str(e)}\nStack trace:\n{traceback.format_exc()}"
            logger.error(error_msg)
            raise

    def clean_daily_factor(self):
        """补全当日数据"""
        try:
            date = datetime.now().strftime('%Y%m%d')
            query = {"date": date}
            records = self.db_handler.mongo_find(self.config["MONGO_DB"], 'stock_market', query)
            if records is None or len(records) == 0:
                logger.info(f"records none for {date}")
                return

            data = pd.DataFrame(list(records))
            data = data[['date', 'symbol', 'open', 'high', 'low', 'close', 'volume']]
            data['order_book_id'] = data['symbol'].apply(get_ricequant_suffix)
            order_book_id_list = data['order_book_id'].tolist()
            logger.info("正在获取市值数据......")
            market_cap_data = rqdatac.get_factor(order_book_ids=order_book_id_list, factor=['market_cap'],start_date=date,end_date=date)
            temp = data.merge(market_cap_data['market_cap'], on='order_book_id', how='left')
            logger.info("正在获取成交额数据......")
            price_data = rqdatac.get_price(order_book_ids=order_book_id_list, start_date=date, end_date=date,
                                           adjust_type='none')
            temp2 = temp.merge(price_data['total_turnover'], on='order_book_id', how='left')
            logger.info("正在获取换手率数据......")
            turnover_data = rqdatac.get_turnover_rate(order_book_ids=order_book_id_list,start_date=date,end_date=date,fields=['today'])
            result_data = temp2.merge(turnover_data['today'], on='order_book_id', how='left')
            result_data = result_data.drop(columns=['order_book_id'])
            result_data = result_data.rename(columns={'today': 'turnover'})
            result_data['market_cap'] = result_data['market_cap'].fillna(0)
            result_data['turnover'] = result_data['turnover'].fillna(0)
            result_data = result_data.rename(columns={'total_turnover': 'amount'})
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

        logger.info("因子数据清洗全部完成！！！")


