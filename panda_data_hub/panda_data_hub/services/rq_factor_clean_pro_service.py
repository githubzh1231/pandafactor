from abc import ABC
from concurrent.futures import ThreadPoolExecutor
from pymongo import UpdateOne
from tqdm import tqdm

import pandas as pd
import rqdatac
import traceback
from datetime import datetime
import time
from panda_common.handlers.database_handler import DatabaseHandler
from panda_common.logger_config import logger
from panda_data_hub.utils.mongo_utils import  ensure_collection_and_indexes
from panda_data_hub.utils.rq_utils import get_ricequant_suffix


class FactorCleanerProService(ABC):

    def __init__(self,config):
        self.config = config
        self.db_handler = DatabaseHandler(config)
        self.progress_callback = None
        try:
            rqdatac.init(config['MUSER'], config['MPASSWORD'])
            logger.info("RiceQuant initialized successfully")
            rqdatac.info()
        except Exception as e:
            error_msg = f"Failed to initialize RiceQuant: {str(e)}\nStack trace:\n{traceback.format_exc()}"
            logger.error(error_msg)
            raise

    def set_progress_callback(self, callback):
        '''进度条实现'''
        self.progress_callback = callback

    def clean_history_data(self, start_date, end_date):
        """补全历史数据"""
        date_range = pd.date_range(start=start_date, end=end_date, freq='D')
        trading_days = []
        for date in date_range:
            date_str = datetime.strftime(date, "%Y-%m-%d")
            trading_days.append(date_str)
        total_days = len(trading_days)
        processed_days = 0
        with tqdm(total=len(trading_days), desc="Processing Trading Days") as pbar:
            # 分批处理，每批5天
            batch_size = 5
            for i in range(0, len(trading_days), batch_size):
                batch_days = trading_days[i:i + batch_size]
                with ThreadPoolExecutor(max_workers=8) as executor:
                    futures = []
                    for date in batch_days:
                        futures.append(
                            executor.submit(
                                self.clean_daily_data,
                                date_str=date,
                                pbar=pbar
                            ))
                    # 等待当前批次的所有任务完成
                    for future in futures:
                        try:
                            future.result()
                            processed_days += 1
                            progress = int((processed_days / total_days) * 100)
                            # 更新进度
                            if self.progress_callback:
                                self.progress_callback(progress)
                            pbar.update(1)
                        except Exception as e:
                            logger.error(f"Task failed: {e}")
                            pbar.update(1)  # 即使任务失败也更新进度条

                # 批次之间添加短暂延迟，避免连接数超限
                if i + batch_size < len(trading_days):
                    logger.info(
                        f"完成批次 {i // batch_size + 1}/{(len(trading_days) - 1) // batch_size + 1}，等待10秒后继续...")
                    time.sleep(10)
        logger.info("因子数据清洗全部完成！！！")

    def clean_daily_data(self, date_str, pbar):
        """补全当日数据"""
        try:
            date = date_str.replace('-', '')
            query = {"date": date}
            records = self.db_handler.mongo_find(self.config["MONGO_DB"], 'stock_market', query)
            if records is None or len(records) == 0:
                logger.info(f"records none for {date}")
                return

            data = pd.DataFrame(list(records))
            data = data[['date', 'symbol', 'open','high','low','close','volume']]
            data['order_book_id'] = data['symbol'].apply(get_ricequant_suffix)
            order_book_id_list = data['order_book_id'].tolist()
            logger.info("正在获取市值数据......")
            market_cap_data = rqdatac.get_factor(order_book_ids=order_book_id_list, factor=['market_cap'], start_date=date,
                                          end_date=date)
            merge_1 = data.merge(market_cap_data['market_cap'], on='order_book_id', how='left')
            logger.info("正在获取成交额数据......")
            price_data = rqdatac.get_price(order_book_ids=order_book_id_list, start_date=date, end_date=date,
                                           adjust_type='none')
            merge_2 = merge_1.merge(price_data['total_turnover'], on='order_book_id', how='left')
            logger.info("正在获取换手率数据......")
            turnover_data = rqdatac.get_turnover_rate(
                order_book_ids=order_book_id_list,
                start_date=date,
                end_date=date,
                fields=['today']
            )
            result_data = merge_2.merge(turnover_data['today'], on='order_book_id', how='left')
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


















