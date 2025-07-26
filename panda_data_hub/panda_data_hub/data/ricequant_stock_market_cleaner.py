from datetime import datetime
from pymongo import UpdateOne
import pandas as pd
import traceback
from abc import ABC
import rqdatac
from panda_common.handlers.database_handler import DatabaseHandler
from panda_common.logger_config import logger
from panda_common.utils.stock_utils import get_exchange_suffix
from panda_data_hub.utils.mongo_utils import ensure_collection_and_indexes


class RQStockMarketCleaner(ABC):
    def __init__(self, config):
        self.config = config
        self.db_handler = DatabaseHandler(config)
        self.hs300_components = None
        self.zz500_components = None
        self.zz1000_components = None
        try:
            rqdatac.init(config['MUSER'], config['MPASSWORD'])
            logger.info("RiceQuant initialized successfully")
            rqdatac.info()
        except Exception as e:
            error_msg = f"Failed to initialize RiceQuant: {str(e)}\nStack trace:\n{traceback.format_exc()}"
            logger.error(error_msg)
            raise

    def stock_market_clean_daily(self):
        logger.info("Starting market data cleaning for rqdatac")
        # 先判断是否为交易日
        date_str = datetime.now().strftime("%Y%m%d")
        if self.is_trading_day(date_str):
            self.clean_meta_market_data(date_str)
        else:
            logger.info(f"跳过非交易日: {date_str}")


    def clean_meta_market_data(self, date_str):
        try:
            # 获取所有股票代码
            symbol_list = rqdatac.all_instruments(type='CS', market='cn', date=None)
            symbol_list = symbol_list[['order_book_id','symbol']]
            #  获取所有日期股票的历史行情
            order_book_id = symbol_list['order_book_id'].tolist()
            price_data = rqdatac.get_price(order_book_ids=order_book_id, start_date=date_str, end_date=date_str,
                                           adjust_type='none')
            price_data = price_data.reset_index()
            # 把名称拼进去
            merged_data = pd.merge(price_data,
                                   symbol_list,
                                   on='order_book_id',
                                   how='left')
            merged_data = merged_data.drop(columns=['num_trades', 'total_turnover'])
            self.get_index_components(start_date = date_str, end_date = date_str)

            # 洗 index_components列
            merged_data['index_component'] = None
            for idx, row in merged_data.iterrows():
                try:
                    component = self.clean_index_components(data_symbol=row['order_book_id'], date=date_str)
                    merged_data.at[idx, 'index_component'] = component
                except Exception as e:
                    logger.error(f"Failed to clean index for {row['order_book_id']} on {date_str}: {str(e)}")
                    continue
            merged_data['date'] = pd.to_datetime(merged_data['date']).dt.strftime("%Y%m%d")
            merged_data = merged_data.rename(columns={"symbol":"name"})
            merged_data = merged_data.rename(columns={'order_book_id': 'symbol'})
            merged_data = merged_data.rename(columns={'prev_close': 'pre_close'})
            merged_data['symbol'] = merged_data['symbol'].apply(get_exchange_suffix)
            # 重新排列
            desired_order = ['date', 'symbol', 'open', 'high', 'low', 'close', 'volume', 'pre_close',
                             'limit_up', 'limit_down', 'index_component', 'name']
            merged_data = merged_data[desired_order]
            ensure_collection_and_indexes("stock_market")
            # 插入数据库
            upsert_operations = []
            for record in merged_data.to_dict('records'):
                upsert_operations.append(UpdateOne(
                    {'date': record['date'], 'symbol': record['symbol']},
                    {'$set': record},
                    upsert=True
                ))
            if upsert_operations:
                self.db_handler.mongo_client[self.config["MONGO_DB"]]['stock_market'].bulk_write(
                    upsert_operations)
                logger.info(f"Successfully upserted market data for date: {date_str}")
        except Exception as e:
            logger.error({e})

    def clean_index_components(self, data_symbol, date):
        try:
            target_date = pd.to_datetime(date)
            # 初始化标记
            # index_mark = '000'
            if self.hs300_components and target_date in self.hs300_components and data_symbol in self.hs300_components[
                target_date]:
                index_mark = '100'
            elif self.zz500_components and target_date in self.zz500_components and data_symbol in \
                    self.zz500_components[target_date]:
                index_mark = '010'
            elif self.zz1000_components and target_date in self.zz1000_components and data_symbol in \
                    self.zz1000_components[target_date]:
                index_mark = '001'
            else:
                index_mark = '000'
            return index_mark
        except Exception as e:
            logger.error(f"Error checking if {data_symbol} is in index components on {date}: {str(e)}")
            return None  # 或者返回其他默认值


    def is_trading_day(self, date):
        """
        判断传入的日期是否为股票交易日

        参数:
        date_str: 日期字符串，格式为 "YYYY-MM-DD"

        返回:
        bool: 如果是交易日返回 True，否则返回 False
        """
        try:
            # 转换日期格式
            date = datetime.strptime(date, "%Y%m%d").strftime("%Y-%m-%d")
            # 获取指定日期的交易日历
            trading_days = rqdatac.get_trading_dates(
                start_date=date,
                end_date=date
            )

            # 如果返回的交易日历不为空，说明是交易日
            return len(trading_days) > 0
        except Exception as e:
            logger.error(f"检查交易日失败 {date}: {str(e)}")
            return False


    def get_index_components(self,start_date, end_date):
        try:
            # 沪深300
            self.hs300_components = rqdatac.index_components('000300.XSHG', start_date = start_date, end_date = end_date)
            # 中证500
            self.zz500_components = rqdatac.index_components('000905.XSHG', start_date = start_date, end_date = end_date)
            # 中证1000
            self.zz1000_components = rqdatac.index_components('000852.XSHG', start_date = start_date, end_date = end_date)

        except Exception as e:
            logger.error(f"Error getting index components: {str(e)}")
            self.components = []
