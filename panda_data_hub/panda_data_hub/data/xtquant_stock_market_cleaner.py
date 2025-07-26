from datetime import datetime

from pymongo import UpdateOne
import pandas as pd
import traceback
from abc import ABC

from xtquant import xtdata
from xtquant import xtdatacenter as xtdc
from panda_common.handlers.database_handler import DatabaseHandler
from panda_common.logger_config import logger
from panda_common.utils.stock_utils import get_exchange_suffix
from panda_data_hub.utils.mongo_utils import ensure_collection_and_indexes
from panda_data_hub.utils.xt_utils import xt_is_trading_day, XTQuantManager


class XTStockMarketCleaner(ABC):
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

    def stock_market_clean_daily(self):
        logger.info("Starting market data cleaning for XTQuant")
        date = datetime.now().strftime("%Y%m%d")
        if xt_is_trading_day(date):
            logger.info(f"今天为交易日，开始更新数据: {date}")
            self.stock_market_daily_clean(date)
        else:
            logger.info(f"今天为非交易日，不予更新数据: {date}")


    def stock_market_daily_clean(self,date):
        try:
            # 获取股票列表
            hs_list = xtdata.get_stock_list_in_sector("沪深A股")
            # 根据列表获取行情数据
            price_data = xtdata.get_market_data_ex(
                field_list=['open', 'close', 'high', 'low', 'volume', 'preClose'], stock_list=hs_list, period='1d',
                start_time=date,
                end_time=date, count=-1, dividend_type='none', fill_data=True)
            # 将行情字典转换为df对象
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
            limit_data = xtdata.get_market_data_ex([], hs_list, period="stoppricedata", start_time=date,
                                                   end_time=date)
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
            name_data = self.clean_stock_market_name(hs_list=hs_list)
            combined_limit = combined_limit.rename(columns={'time': 'date'})
            combined_limit = combined_limit.rename(columns={'涨停价': 'limit_up'})
            combined_limit = combined_limit.rename(columns={'跌停价': 'limit_down'})
            combined_limit = combined_limit[['stock_code', 'date', 'limit_up', 'limit_down']]
            merged_df = pd.merge(
                combined_price,
                combined_limit[['stock_code', 'date', 'limit_up', 'limit_down']],  # 只选择需要的列
                on=['stock_code', 'date'],  # 合并键
                how='left',  # 保留所有combined_df的数据
            )
            final_df = pd.merge(
                merged_df,
                name_data[['stock_code', 'InstrumentName']],
                on=['stock_code'],
                how='left',
            )
            # 迅投SDK获取历史成分股数据的接口需单独定制
            final_df['index_component'] = 111
            final_df = final_df.rename(columns={'stock_code': 'symbol'})
            final_df['symbol'] = final_df['symbol'].apply(get_exchange_suffix)
            final_df = final_df.rename(columns={'InstrumentName': 'name'})
            final_df = final_df.rename(columns={'preClose': 'pre_close'})
            final_df['volume'] = final_df['volume'] * 100
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
                logger.info(f"Successfully upserted market data for date: {date}")

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