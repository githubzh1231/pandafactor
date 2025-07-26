import calendar
from abc import ABC
import tushare as ts
from pymongo import UpdateOne
import traceback
from datetime import datetime
from panda_common.handlers.database_handler import DatabaseHandler
from panda_common.logger_config import logger
from panda_common.utils.stock_utils import get_exchange_suffix
from panda_data_hub.utils.mongo_utils import ensure_collection_and_indexes
from panda_data_hub.utils.ts_utils import calculate_upper_limit, calculate_lower_limit


class TSStockMarketCleaner(ABC):
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

    def stock_market_clean_daily(self):

        logger.info("Starting market data cleaning for tushare")
        # 先判断是否为交易日
        date_str = datetime.now().strftime("%Y%m%d")
        if self.is_trading_day(date_str):
            self.clean_meta_market_data(date_str)
        else:
            logger.info(f"跳过非交易日: {date_str}")

    def clean_meta_market_data(self,date_str):
        try:
            date = date_str.replace("-", "")
            #  获取当日股票的历史行情
            price_data = self.pro.query('daily', trade_date=date)
            # 重置股票行情数据索引
            price_data.reset_index(drop=False, inplace=True)
            # 洗 index_components列
            price_data['index_component'] = None

            # 根据date获取当月最后一个交易日
            mid_date,last_date = self.get_previous_month_dates(date)
            # 沪深300成分股
            hs_300 = self.pro.query('index_weight', index_code='399300.SZ', start_date=mid_date, end_date=last_date)
            # 中证500成分股
            zz_500 = self.pro.query('index_weight', index_code='000905.SH', start_date=mid_date, end_date=last_date)
            # 中证1000成分股
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
            price_data['name'] = price_data['ts_code'].apply(self.clean_stock_name)
            price_data = price_data.drop(columns=['index','change','pct_chg','amount'])
            price_data = price_data.rename(columns={'vol': 'volume'})
            price_data = price_data.rename(columns={'trade_date': 'date'})
            price_data['ts_code'] = price_data['ts_code'].apply(get_exchange_suffix)
            price_data = price_data.rename(columns={'ts_code': 'symbol'})
            # 计算涨跌停价格
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
            price_data['volume'] = price_data['volume'] * 100
            desired_order = ['date', 'symbol', 'open', 'high', 'low', 'close', 'volume', 'pre_close',
                             'limit_up', 'limit_down', 'index_component', 'name']
            price_data = price_data[desired_order]
            # 过滤掉北交所的股票
            price_data = price_data[~price_data['symbol'].str.contains('BJ')]
            ensure_collection_and_indexes(table_name='stock_market')
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
                logger.info(f"Successfully upserted market data for date: {date}")

        except Exception as e:
            logger.error({e})

    def clean_index_components(self, date, data_symbol, hs_300, zz_500, zz_1000):
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

    def clean_stock_name(self, data_symbol):
        logger.info(f"Success to clean name for {data_symbol}")
        stock_info  = self.pro.query('stock_basic',ts_code = data_symbol, list_status='L')
        current_name = stock_info['name'].iloc[0]
        return current_name

    def is_trading_day(self, date):
        """
        判断传入的日期是否为股票交易日

        参数:
        date: 日期字符串，格式为 "YYYY-MM-DD"

        返回:
        bool: 如果是交易日返回 True，否则返回 False
        """
        try:
            # 获取指定日期的交易日历信息
            cal_df = self.pro.query('trade_cal',
                                    exchange='SSE',
                                    start_date=date.replace('-', ''),
                                    end_date=date.replace('-', ''))
            # 检查是否有数据返回及该日期是否为交易日(is_open=1表示交易日)
            if not cal_df.empty and cal_df.iloc[0]['is_open'] == 1:
                return True
            return False
        except Exception as e:
            logger.error(f"检查交易日失败 {date}: {str(e)}")
            return False

    def get_previous_month_dates(self,date_str):
        """
        根据日期字符串获取上个月的中间日和最后一日
        参数格式：'YYYYMMDD' (如 '20170101')
        返回值：(中间日字符串, 最后一日字符串)
        """
        # 转换为datetime对象
        date = datetime.strptime(date_str, "%Y%m%d")
        year = date.year
        month = date.month

        # 计算上个月的年份和月份
        if month == 1:
            prev_year = year - 1
            prev_month = 12
        else:
            prev_year = year
            prev_month = month - 1

        # 获取上个月最后一天
        last_day = calendar.monthrange(prev_year, prev_month)[1]
        last_date = f"{prev_year}{prev_month:02d}{last_day:02d}"

        # 计算中间日（向上取整）
        middle_day = (last_day + 1) // 2
        middle_date = f"{prev_year}{prev_month:02d}{middle_day:02d}"

        return middle_date, last_date