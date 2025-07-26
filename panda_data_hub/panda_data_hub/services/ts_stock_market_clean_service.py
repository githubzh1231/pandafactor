from abc import ABC


import tushare as ts
from pymongo import UpdateOne
import traceback

import pandas as pd
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor
from tqdm import tqdm
import time

from panda_common.handlers.database_handler import DatabaseHandler
from panda_common.logger_config import logger
from panda_common.utils.stock_utils import get_exchange_suffix
from panda_data_hub.utils.mongo_utils import ensure_collection_and_indexes
from panda_data_hub.utils.ts_utils import calculate_upper_limit, ts_is_trading_day, get_previous_month_dates, \
    calculate_lower_limit

"""
       使用须知：因tushare对于接口返回数据条数具有严格限制，故无法一次拉取全量数据。此限制会导致接口运行效率偏低，请耐心等待。

       参数:
       date: 日期字符串，格式为 "YYYY-MM-DD"

       返回:
       bool: 如果是交易日返回 True，否则返回 False
       """


class StockMarketCleanTSServicePRO(ABC):
    def __init__(self, config):
        self.config = config
        self.db_handler = DatabaseHandler(config)
        self.progress_callback = None
        try:
            ts.set_token(config['TS_TOKEN'])
            self.pro = ts.pro_api()
        except Exception as e:
            error_msg = f"Failed to initialize tushare: {str(e)}\nStack trace:\n{traceback.format_exc()}"
            logger.error(error_msg)
            raise

    def set_progress_callback(self, callback):
        self.progress_callback = callback

    def stock_market_history_clean(self, start_date, end_date):

        logger.info("Starting market data cleaning for tushare")

        # 获取交易日
        date_range = pd.date_range(start=start_date, end=end_date, freq='D')
        trading_days = []
        for date in date_range:
            date_str = datetime.strftime(date, "%Y-%m-%d")
            if ts_is_trading_day(date_str):
                trading_days.append(date_str)
            else:
                logger.info(f"跳过非交易日: {date_str}")
        logger.info(f"找到 {len(trading_days)} 个交易日需要处理")
        total_days = len(trading_days)
        processed_days = 0
        # 根据交易日去循环
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
                            date_str=date
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
        logger.info("所有交易日数据处理完成")

    def clean_meta_market_data(self,date_str):
        try:
            date = date_str.replace("-", "")
            #  获取当日股票的历史行情
            price_data = self.pro.query('daily', trade_date=date)
            # 重置股票行情数据索引
            price_data.reset_index(drop=False, inplace=True)
            # 洗 index_components列
            price_data['index_component'] = None

            # tushare关于中证500和中证1000这两个指数只有每月的最后一个交易日才有数据，对于沪深300成分股是每月的第一个交易日和最后一个交易日才有数据
            # 根据日期获取当月三个指数的
            mid_date,last_date = get_previous_month_dates(date_str = date)
            # 沪深300
            hs_300 = self.pro.query('index_weight', index_code='399300.SZ', start_date=mid_date, end_date=last_date)
            # 中证500
            zz_500 = self.pro.query('index_weight', index_code='000905.SH', start_date=mid_date, end_date=last_date)
            # 中证1000
            zz_1000 = self.pro.query('index_weight', index_code='000852.SH', start_date=mid_date, end_date=last_date)
            for idx, row in price_data.iterrows():
                try:
                    component = self.clean_index_components(data_symbol=row['ts_code'], date=date,hs_300 =hs_300,zz_500 = zz_500,zz_1000 = zz_1000)
                    price_data.at[idx, 'index_component'] = component
                    logger.info(f"Success to clean index for {row['ts_code']} on {date}")
                except Exception as e:
                    logger.error(f"Failed to clean index for {row['ts_code']} on {date}: {str(e)}")
                    continue
            # 洗name列
            # 报错ERROR - Error checking if ****** on date: single positional indexer is out-of-bounds，说明该股票已经退市
            price_data['name'] = None
            # 获取历史名称变更信息
            # end_date = 20250423的数据条数一共是7413,接口最多返回10000条数据，目前是足够的
            namechange_info = self.pro.query('namechange', end_date=date)
            #获取目前所有股票的名称
            stock_info = self.pro.query('stock_basic')
            for idx, row in price_data.iterrows():
                try:
                    stock_name = self.clean_stock_name(data_symbol=row['ts_code'], date=date,namechange_info = namechange_info,stock_info = stock_info)
                    price_data.at[idx, 'name'] = stock_name
                    # logger.info(f"Success to clean name for {row['ts_code']} on {date}")
                except Exception as e:
                    logger.error(f"Failed to clean name for {row['ts_code']} on {date}: {str(e)}")
                    continue
            price_data = price_data.drop(columns=['index','change','pct_chg','amount'])
            price_data = price_data.rename(columns={'vol': 'volume'})
            price_data = price_data.rename(columns={'trade_date': 'date'})
            price_data['ts_code'] = price_data['ts_code'].apply(get_exchange_suffix)
            price_data = price_data.rename(columns={'ts_code': 'symbol'})

            # 计算涨跌停价格时对于已经退市的股票，因无法获取当日股票名称，故无法计算涨跌停价格
            price_data['limit_up'] = None
            price_data['limit_down'] = None
            price_data['limit_up'] = price_data.apply(
                lambda row: calculate_upper_limit(stock_code = row['symbol'], prev_close = row['pre_close'], stock_name = row['name']),
                axis=1
            )
            price_data['limit_down'] = price_data.apply(
                lambda row: calculate_lower_limit(stock_code = row['symbol'], prev_close = row['pre_close'], stock_name = row['name']),
                axis=1
            )
            price_data['volume'] = price_data['volume']*100
            # 过滤掉北交所的股票
            price_data = price_data[~price_data['symbol'].str.contains('BJ')]
            #重新排列
            desired_order = ['date', 'symbol', 'open', 'high', 'low', 'close', 'volume', 'pre_close',
                             'limit_up', 'limit_down', 'index_component', 'name']
            price_data = price_data[desired_order]
            # 检索数据库索引
            ensure_collection_and_indexes(table_name='stock_market')
            # 执行插入操作
            upsert_operations = []
            for record in price_data.to_dict('records'):
                upsert_operations.append(UpdateOne(
                    {'date': record['date'], 'symbol': record['symbol']},
                    {'$set': record},
                    upsert=True
                ))
            if upsert_operations:
                self.db_handler.mongo_client[self.config["MONGO_DB"]]['stock_market'].bulk_write(
                    upsert_operations)
                # logger.info(f"Successfully upserted market data for date: {date}")

        except Exception as e:
            logger.error({e})

    def clean_index_components(self, date,data_symbol, hs_300,zz_500 ,zz_1000):
        try:
            # 首先查询沪深300
            if data_symbol in hs_300['con_code'].values:
                return '100'

            # 如果不在沪深300中，查询中证500
            if data_symbol in zz_500['con_code'].values:
                return '010'

            # 如果不在中证500中，查询中证1000
            if data_symbol in zz_1000['con_code'].values:
                return '001'

            # 如果都不在其中
            return '000'

        except Exception as e:
            logger.error(f"Error checking if {data_symbol} is in index components on {date}: {str(e)}")
            return None

    def clean_stock_name(self, data_symbol, date,namechange_info,stock_info):
        try:
            # 获取某只股票的换名历史
            valid_changes = namechange_info[(namechange_info['ann_date'] <= date) &(namechange_info['ts_code'] == data_symbol)]
            if not valid_changes.empty:
                # 按开始日期排序，获取最新的变更记录
                latest_change = valid_changes.sort_values('ann_date', ascending=False).iloc[0]
                latest_symbol = latest_change['name']
                return latest_symbol
            else:
                current_info = stock_info[stock_info['ts_code'] == data_symbol]
                current_name = current_info['name'].iloc[0]
                return current_name

        except Exception as e:
            logger.error(f"Error checking if {data_symbol} on {date}: {str(e)}")
            return None  # 或者返回其他默认值



