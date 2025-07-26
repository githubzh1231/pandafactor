import time
from datetime import datetime
from pymongo import UpdateOne
from tqdm import tqdm
import pandas as pd
import traceback
from abc import ABC
from concurrent.futures import ThreadPoolExecutor
from xtquant import xtdata

from panda_common.handlers.database_handler import DatabaseHandler
from panda_common.logger_config import logger
from panda_common.utils.stock_utils import get_exchange_suffix
from panda_data_hub.utils.mongo_utils import ensure_collection_and_indexes
from panda_data_hub.utils.xt_utils import xt_is_trading_day, XTQuantManager


class StockMarketCleanXTServicePRO(ABC):
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

    def set_progress_callback(self, callback):
        self.progress_callback = callback
    def stock_market_history_clean(self, start_date, end_date):

        logger.info("Starting market data cleaning for XTQuant")

        # 1. 获取交易日
        date_range = pd.date_range(start=start_date, end=end_date, freq='D')
        trading_days = []
        for date in date_range:
            date_str = datetime.strftime(date, "%Y-%m-%d")
            if xt_is_trading_day(date_str):
                trading_days.append(date_str)
            else:
                logger.info(f"跳过非交易日: {date_str}")
        if len(trading_days) == 0:
            logger.info("该时间范围内没有找到交易日")
            return
        total_days = len(trading_days)
        processed_days = 0
        logger.info(f"找到 {len(trading_days)} 个交易日需要处理")
        # 2. 获取股票交易行情
        hs_list = xtdata.get_stock_list_in_sector("沪深A股")
        price_data = xtdata.get_market_data_ex(
            field_list=['open', 'close', 'high', 'low', 'volume', 'preClose'], stock_list=hs_list, period='1d',start_time=start_date,
            end_time=end_date,count=-1,dividend_type='none',fill_data=True)

        # 将股票交易行情转换成df对象
        dfs_price = []
        for stock_code, df in price_data.items():
            # 过滤掉 open 列为 NaN 的行（行级别过滤）
            df_clean = df.dropna(subset=['open'])  # 只处理 open 列存在 NaN 的行

            # 如果过滤后的 DataFrame 为空，跳过（可选逻辑）
            if df_clean.empty:
                continue
            df['stock_code'] = stock_code  # 添加股票代码列
            df['date'] = df.index  # 把索引变成列
            dfs_price.append(df)
        if len(dfs_price) == 0:
            logger.info("没有获取到股票历史行情")
            return
        combined_price = pd.concat(dfs_price, ignore_index=True)
        combined_price = combined_price[['stock_code', 'date', 'open', 'high', 'low', 'close', 'volume', 'preClose']]
        # 3. 获取所有股票历史涨跌停价格
        limit_data = xtdata.get_market_data_ex([], hs_list, period="stoppricedata", start_time=start_date,end_time=end_date)
        # 将limit_data转换成df
        dfs_limit = []
        for stock_code, df in limit_data.items():
            df['stock_code'] = stock_code  # 添加股票代码列
            dfs_limit.append(df)
        combined_limit = pd.concat(dfs_limit, ignore_index=True)
        combined_limit['time'] = (
            (pd.to_datetime(combined_limit['time'], unit='ms')  # 解析为UTC时间
             + pd.Timedelta(hours=8))  # 转换为UTC+8（北京时间）
            .dt.strftime('%Y%m%d')  # 格式化为YYYYMMDD
        )
        combined_limit = combined_limit[['stock_code', 'time', '涨停价', '跌停价']]
        # 获取股票名称
        name_data = self.clean_stock_market_name(hs_list = hs_list)
        # 根据交易日去循环
        with tqdm(total=len(trading_days), desc="Processing Trading Days") as pbar:
            # 分批处理，每批10天
            batch_size = 10
            for i in range(0, len(trading_days), batch_size):
                batch_days = trading_days[i:i + batch_size]
                with ThreadPoolExecutor(max_workers=10) as executor:
                    futures = []
                    for date in batch_days:
                        date_str = date.replace("-","")
                        price_daily_data = combined_price[combined_price['date'] == date_str]
                        limit_daily_data = combined_limit[combined_limit['time'] == date_str]
                        futures.append(executor.submit(
                            self.clean_meta_market_data,
                            price_data = price_daily_data,
                            limit_data = limit_daily_data,
                            name_data=name_data,
                            date_str = date_str
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
                            pbar.update(1)  # 更新进度条
                        except Exception as e:
                            logger.error(f"Task failed: {e}")
                            pbar.update(1)  # 即使任务失败也更新进度条

                # 批次之间添加短暂延迟，避免连接数超限
                if i + batch_size < len(trading_days):
                    logger.info(
                        f"完成批次 {i // batch_size + 1}/{(len(trading_days) - 1) // batch_size + 1}，等待10秒后继续...")
                    time.sleep(3)
        logger.info("所有交易日数据处理完成")


    def clean_meta_market_data(self, price_data,limit_data,name_data,date_str):
        try:
            limit_data = limit_data.rename(columns={'time': 'date'})
            limit_data = limit_data.rename(columns={'涨停价': 'limit_up'})
            limit_data = limit_data.rename(columns={'跌停价': 'limit_down'})
            limit_data = limit_data[['stock_code', 'date', 'limit_up', 'limit_down']]
            merged_df = pd.merge(
                price_data,
                limit_data[['stock_code', 'date', 'limit_up', 'limit_down']],  # 只选择需要的列
                on=['stock_code', 'date'],  # 合并键
                how='left',  # 保留所有combined_df的数据
            )
            final_df = pd.merge(
                merged_df,
                name_data[['stock_code','InstrumentName']],
                on=['stock_code'],
                how='left',
            )
            # 迅投SDK获取历史成分股数据的接口需单独定制
            final_df['index_component'] = 111
            final_df = final_df.rename(columns={'stock_code': 'symbol'})
            final_df['symbol'] = final_df['symbol'].apply(get_exchange_suffix)
            final_df = final_df.rename(columns={'InstrumentName': 'name'})
            final_df = final_df.rename(columns={'preClose': 'pre_close'})
            final_df['volume'] = final_df['volume']*100
            desired_order = ['date', 'symbol', 'open', 'high', 'low', 'close', 'volume', 'pre_close',
                             'limit_up', 'limit_down', 'index_component', 'name']
            final_df = final_df[desired_order]
            # 入库前创建集合及索引
            ensure_collection_and_indexes("stock_market")
            # 入库
            upsert_operations = []
            for record in final_df.to_dict('records'):
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

    def clean_stock_market_name(self,hs_list):
        try:
            stock_details = []
            for stock_code in hs_list:
                detail = xtdata.get_instrument_detail(stock_code)
                if detail:  # 确保接口返回有效数据
                    detail['stock_code'] = stock_code  # 添加股票代码到详情中
                    stock_details.append(detail)

            df_details = pd.DataFrame(stock_details)
            df_details = df_details[['stock_code', 'InstrumentName']]
            return df_details
        except Exception as e:
            error_msg = f"Failed to initialize XtQuant: {str(e)}\nStack trace:\n{traceback.format_exc()}"
            logger.error(error_msg)
            raise

