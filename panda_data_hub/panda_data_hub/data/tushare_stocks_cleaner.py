import traceback
from abc import ABC
from panda_common.handlers.database_handler import DatabaseHandler
from panda_common.logger_config import logger
from panda_common.utils.stock_utils import get_exchange_suffix
import tushare as ts


class TSStockCleaner(ABC):

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

    def clean_metadata(self):
        try:
            logger.info("Starting metadata cleaning for Tushare")
            stocks = self.pro.query('stock_basic')
            stocks = stocks[['ts_code', 'name']]
            stocks = stocks[stocks["name"] != "UNKNOWN"]
            stocks['symbol'] = stocks['ts_code'].apply(get_exchange_suffix)
            stocks = stocks.drop(columns=['ts_code'])
            stocks['expired'] = False
            desired_order = ['symbol', 'name', 'expired']
            stocks = stocks[desired_order]

            logger.info("Updating MongoDB stocks collection")
            # 清空现有的stocks集合
            self.db_handler.mongo_delete(self.config["MONGO_DB"], 'stocks', {})
            # 将处理后的股票数据批量插入到MongoDB
            self.db_handler.mongo_insert_many(
                self.config["MONGO_DB"],
                'stocks',
                stocks.to_dict('records')
            )
            logger.info("Successfully updated stocks metadata")
        except Exception as e:
            # 错误处理：记录详细的错误信息和堆栈跟踪
            error_msg = f"Failed to clean metadata: {str(e)}\nStack trace:\n{traceback.format_exc()}"
            logger.error(error_msg)
            raise  # 重新抛出异常，让上层代码处理

