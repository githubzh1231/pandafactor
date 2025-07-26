import traceback
from abc import ABC
from xtquant import xtdata
import time
from panda_common.logger_config import logger
from panda_data_hub.utils.xt_utils import XTQuantManager


class XTDownloadService(ABC):
    def __init__(self,config):
        self.config = config
        self.progress_callback = None
        try:
            XTQuantManager.get_instance(config)
            logger.info("XtQuant ready to use")
        except Exception as e:
            error_msg = f"Failed to initialize XtQuant: {str(e)}\nStack trace:\n{traceback.format_exc()}"
            logger.error(error_msg)
            raise

    def set_progress_callback(self, callback):
        """设置进度回调函数"""
        self.progress_callback = callback

    def xt_price_data_download(self, start_date, end_date):
        """单线程顺序下载数据（带进度回调）"""
        try:
            # 获取股票列表
            hs_list = xtdata.get_stock_list_in_sector("沪深A股")
            total = len(hs_list)
            completed = 0
            
            for stock_code in hs_list:
                try:
                    # 下载历史K线
                    xtdata.download_history_data(stock_code, '1d', start_time=start_date, end_time=end_date)
                    # 下载涨跌停价格
                    xtdata.download_history_data(stock_code, 'stoppricedata', start_time=start_date, end_time=end_date)
                    
                    # 更新进度
                    completed += 1
                    progress = int((completed / total) * 100)
                    if self.progress_callback:
                        self.progress_callback(progress)

                    logger.info(f"已下载 {stock_code}，进度: {progress}%")
                    time.sleep(0.1)  # 避免请求过于频繁
                except Exception as e:
                    logger.error(f"下载 {stock_code} 失败: {e}")
                    continue  # 继续下载下一个股票

            logger.info("全部下载完成！")
            if self.progress_callback:
                self.progress_callback(100)  # 确保最终进度为100%

        except Exception as e:
            logger.error(f"下载过程发生错误: {e}")
            if self.progress_callback:
                self.progress_callback(-1)  # 错误信号
            raise  # 重新抛出异常以便上层处理