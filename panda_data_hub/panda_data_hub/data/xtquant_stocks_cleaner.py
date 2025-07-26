from datetime import datetime
import pandas as pd
import traceback
from abc import ABC
from xtquant import xtdata
from xtquant import xtdatacenter as xtdc
from panda_common.handlers.database_handler import DatabaseHandler
from panda_common.logger_config import logger
from panda_common.utils.stock_utils import get_exchange_suffix
from panda_data_hub.services.xt_download_service import XTDownloadService
from panda_data_hub.utils.xt_utils import XTQuantManager, get_stock_name


class XTStockCleaner(ABC):
    def __init__(self, config):
        self.config = config
        self.db_handler = DatabaseHandler(config)
        self.xt_downloader = XTDownloadService(config)
        try:
            XTQuantManager.get_instance(config)
            logger.info("XtQuant ready to use")
        except Exception as e:
            error_msg = f"Failed to initialize XtQuant: {str(e)}\nStack trace:\n{traceback.format_exc()}"
            logger.error(error_msg)
            raise

    def clean_metadata(self):
        try:
            logger.info("Starting metadata cleaning for XTQuant")
            date = datetime.now().strftime("%Y%m%d")
            # 先将数据下载到本地
            logger.info("开始下载数据！！！")
            self.xt_downloader.xt_price_data_download(start_date=date, end_date=date)
            # 获取股票列表
            logger.info("开始清洗数据！！！")
            stocks_list = xtdata.get_stock_list_in_sector("沪深A股")
            stocks = pd.DataFrame({'stock_code': stocks_list})
            stocks['symbol'] = stocks['stock_code'].apply(get_exchange_suffix)
            stocks['expired'] = False
            stocks['name'] = stocks['stock_code'].apply(get_stock_name)
            stocks = stocks.rename(columns={'stock_code':'instrument_id'})
            stocks = stocks.drop(columns=['instrument_id'])
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






















