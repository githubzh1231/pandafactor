from xtquant import xtdata
from panda_common.logger_config import logger
from xtquant import xtdatacenter as xtdc
class XTQuantManager:
    _instance = None
    _initialized = False
    _token = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super(XTQuantManager, cls).__new__(cls)
        return cls._instance

    def __init__(self, config):
        if not self._initialized and config is not None:
            try:
                # 只在第一次初始化时设置token和初始化
                if self._token != config['XT_TOKEN']:
                    self._token = config['XT_TOKEN']
                    xtdc.set_token(self._token)
                    xtdc.init()
                    self._initialized = True
                    logger.info("XtQuant initialized successfully")
            except Exception as e:
                error_msg = f"Failed to initialize XtQuant: {str(e)}"
                logger.error(error_msg)
                raise

    @classmethod
    def get_instance(cls, config=None):
        if cls._instance is None:
            cls._instance = cls(config)
        elif config is not None and not cls._initialized:
            cls._instance.__init__(config)
        return cls._instance

def xt_is_trading_day(date):
    """
    判断传入的日期是否为股票交易日

    参数:
    date: 日期字符串，格式为 "YYYY-MM-DD"

    返回:
    bool: 如果是交易日返回 True，否则返回 False
    """
    try:
        # 将日期格式转换为讯投要求的格式（YYYYMMDD）
        date_str = date.replace('-', '')

        # 获取指定日期的交易日历
        trading_dates = xtdata.get_trading_dates(market = 'SH',start_time = date_str, end_time = date_str)

        # 如果trading_dates列表不为空，说明是交易日，返回True
        # 如果trading_dates列表为空，说明不是交易日，返回False
        return len(trading_dates) > 0

    except Exception as e:
        logger.error(f"检查交易日失败 {date}: {str(e)}")
        # 发生异常时返回False
        return False


def get_xt_suffix(code):
    code = code.split('.')[0]

    # 上交所股票
    if code.startswith(("600", "601", "603", "688", "689", "605", "900")):
        return f"{code}.SH"

    # 深交所股票
    elif code.startswith(("000", "001", "002", "003", "300", "301")):
        return f"{code}.SZ"

    # 北交所股票
    elif code.startswith(("43", "83", "87", "920")):
        return f"{code}.BJ"

    # 其他情况（如指数、基金等）
    else:
        return "UNKNOWN"
        # # 特殊处理常见指数
        # if code in ["000001", "399001", "399006"]:
        #     return f"{code}.SH" if code == "000001" else f"{code}.SZ"
        # return code  # 不加后缀


def xt_get_total_volume(stock_code):
    try:
        detail = xtdata.get_instrument_detail(stock_code)
        total_volume = detail.get('TotalVolume')
        return total_volume if detail else None
    except Exception as e:
        logger.error(f"Error getting detail for {stock_code}: {str(e)}")
        return None

def xt_get_amount(stock_code,date):
    try:
        price_data = xtdata.get_market_data_ex(
            field_list=['amount'], stock_list=[stock_code], period='1d',
            start_time=date,
            end_time=date, count=-1, dividend_type='none', fill_data=True)
        return float(price_data[stock_code]['amount'][date])
    except Exception as e:
        logger.error(f"Error getting amount for {stock_code}: {str(e)}")
        return 0

def get_stock_name(stock_code):
    try:
        detail = xtdata.get_instrument_detail(stock_code)
        stock_name = detail["InstrumentName"]
        return stock_name
    except Exception as e:
        logger.error(f"Error getting amount for {stock_code}: {str(e)}")
        return 0