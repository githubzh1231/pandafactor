import time
from datetime import datetime

from pymongo import UpdateOne

from tqdm import tqdm
import pandas as pd
import traceback
from abc import ABC
import rqdatac
from concurrent.futures import ThreadPoolExecutor
from panda_common.handlers.database_handler import DatabaseHandler
from panda_common.logger_config import logger
from panda_common.utils.stock_utils import get_exchange_suffix
from panda_data_hub.utils.mongo_utils import ensure_collection_and_indexes
from panda_data_hub.utils.rq_utils import get_index_components, rq_is_trading_day


class StockMarketCleanRQServicePRO(ABC):

    def __init__(self, config):
        self.config = config
        self.db_handler = DatabaseHandler(config)
        self.hs300_components = None
        self.zz500_components = None
        self.zz1000_components = None
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
        self.progress_callback = callback

    def stock_market_clean_by_time(self, start_date, end_date):

        logger.info("Starting market data cleaning for rqdatac")
        # 获取所有股票代码
        symbol_list = rqdatac.all_instruments(type='CS', market='cn', date=None)
        symbol_list = symbol_list['order_book_id']
        #  获取所有日期股票的历史行情
        price_data = rqdatac.get_price(order_book_ids=symbol_list, start_date=start_date, end_date=end_date,adjust_type='none')
        # 获取所有日期的所有股票的历史名称变更信息
        symbol_change_info = rqdatac.get_symbol_change_info(symbol_list)
        # 获取所有日期的指数成分股票
        self.hs300_components,self.zz500_components,self.zz1000_components = get_index_components(start_date, end_date)
        # 获取交易日
        date_range = pd.date_range(start=start_date, end=end_date, freq='D')
        trading_days = []
        for date in date_range:
            date_str = datetime.strftime(date, "%Y-%m-%d")
            if rq_is_trading_day(date_str):
                trading_days.append(date_str)
            else:
                logger.info(f"跳过非交易日: {date_str}")
        logger.info(f"找到 {len(trading_days)} 个交易日需要处理")
        # 根据交易日去循环
        total_days = len(trading_days)
        processed_days = 0
        with tqdm(total=len(trading_days), desc="Processing Trading Days") as pbar:
            # 分批处理，每批8天
            batch_size = 8
            for i in range(0, len(trading_days), batch_size):
                batch_days = trading_days[i:i + batch_size]
                with ThreadPoolExecutor(max_workers=10) as executor:
                    futures = []
                    for date in batch_days:
                        futures.append(executor.submit(
                            self.clean_meta_market_data,
                            price_data_origin = price_data,
                            symbol_change_info_origin = symbol_change_info,
                            date = date
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
                        f"完成批次 {i // batch_size + 1}/{(len(trading_days) - 1) // batch_size + 1}，等待5秒后继续...")
                    time.sleep(5)

        logger.info("所有交易日数据处理完成")

    def clean_meta_market_data(self,price_data_origin, symbol_change_info_origin,date):
        try:
            # 为保证线程安全，特此加上副本
            price_data = price_data_origin.copy()
            symbol_change_info =symbol_change_info_origin.copy()
            # 重置股票行情数据索引
            price_data.reset_index(drop=False,inplace=True)
            symbol_change_info.reset_index(drop=False, inplace=True)
            # 获得指定日期的股票行情数据
            price_daily_data = price_data[price_data['date'] == date]

            # 洗 index_components列
            price_daily_data['index_component'] = None
            for idx, row in price_daily_data.iterrows():
                try:
                    component = self.clean_index_components(data_symbol=row['order_book_id'],date=date)
                    price_daily_data.at[idx, 'index_component'] = component
                except Exception as e:
                    logger.error(f"Failed to clean index for {row['order_book_id']} on {date}: {str(e)}")
                    continue

            # 洗name列
            price_daily_data['name'] = None
            for idx, row in price_daily_data.iterrows():
                try:
                    stock_name = self.clean_stock_name(symbol_change_info = symbol_change_info,data_symbol=row['order_book_id'], date=date)
                    price_daily_data.at[idx, 'name'] = stock_name
                except Exception as e:
                    logger.error(f"Failed to clean index for {row['order_book_id']} on {date}: {str(e)}")
                    continue

            # 洗其他列
            price_daily_data = price_daily_data.drop(columns=['num_trades', 'total_turnover'])
            price_daily_data['date'] = pd.to_datetime(price_daily_data['date']).dt.strftime("%Y%m%d")
            price_daily_data = price_daily_data.rename(columns={'order_book_id': 'symbol'})
            price_daily_data = price_daily_data.rename(columns={'prev_close': 'pre_close'})
            price_daily_data['symbol'] = price_daily_data['symbol'].apply(get_exchange_suffix)
            desired_order = ['date', 'symbol', 'open', 'high', 'low', 'close', 'volume', 'pre_close',
                             'limit_up', 'limit_down', 'index_component', 'name']
            price_daily_data = price_daily_data[desired_order]
            # 检索数据库索引
            ensure_collection_and_indexes(table_name = 'stock_market')
            # 执行插入操作
            upsert_operations = []
            for record in price_daily_data.to_dict('records'):
                upsert_operations.append(UpdateOne(
                    {'date': record['date'], 'symbol': record['symbol']},
                    {'$set': record},
                    upsert=True
                ))
            if upsert_operations:
                self.db_handler.mongo_client[self.config["MONGO_DB"]]['stock_market'].bulk_write(
                    upsert_operations)
                logger.info(f"Successfully upserted market data for date: {date}")

        except Exception as e:
            logger.error({e})

    def clean_index_components(self,data_symbol,date):
        try:
            target_date = pd.to_datetime(date)
            # 初始化标记
            # index_mark = '000'
            if self.hs300_components and target_date in self.hs300_components and data_symbol in self.hs300_components[target_date]:
                index_mark = '100'
            elif  self.zz500_components and target_date in self.zz500_components and data_symbol in self.zz500_components[target_date]:
                index_mark = '010'
            elif self.zz1000_components and target_date in self.zz1000_components and data_symbol in self.zz1000_components[target_date]:
                index_mark = '001'
            else:
                index_mark = '000'
            return index_mark
        except Exception as e:
            logger.error(f"Error checking if {data_symbol} is in index components on {date}: {str(e)}")
            return None  # 或者返回其他默认值


    def clean_stock_name(self,symbol_change_info,data_symbol,date):
        try:
            daily_info = symbol_change_info[symbol_change_info['order_book_id'] == data_symbol]

            valid_changes = daily_info[daily_info['change_date'] <= date]
            if not valid_changes.empty:
                # 按开始日期排序，获取最新的变更记录
                # valid_changes.reset_index(inplace=True, drop=False)
                latest_change = valid_changes.sort_values('change_date', ascending=False).iloc[0]
                latest_symbol = latest_change['symbol']
                return latest_symbol
            else:
                stock_info = rqdatac.instruments(order_book_ids=data_symbol)
                current_name = stock_info.symbol
                return current_name

        except Exception as e:
            logger.error(f"Error checking if {data_symbol} is in index components on {date}: {str(e)}")
            return None  # 或者返回其他默认值