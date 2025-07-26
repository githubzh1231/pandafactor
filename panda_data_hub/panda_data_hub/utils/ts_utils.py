import logging
import calendar
from datetime import datetime
import tushare as ts

# 设置日志记录器
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

def calculate_upper_limit(stock_code, prev_close, stock_name):
    """
    根据股票代码、前收盘价和股票名称计算涨停价格。

    Args:
        stock_code (str): 股票代码 (纯数字部分，如 '600000').
        prev_close (float): 前一交易日收盘价.
        stock_name (str): 股票名称 (用于判断ST).

    Returns:
        float or None: 涨停价格，如果无法确定则返回 None.
    """
    if not isinstance(prev_close, (int, float)) or prev_close <= 0:
        logger.warning(f"无效的前收盘价: {prev_close} for stock {stock_code}")
        return None
    # 对于历史行情中已经退市的股票，其股票名称为Nan
    if stock_name is None:
        return None

    market_type = get_stock_market_type(stock_code)

    if market_type == 'main':
        # 主板: 正常 ±10%, ST ±5%
        limit_factor = 1.05 if 'ST' in stock_name or '*ST' in stock_name else 1.10
        return round(prev_close * limit_factor, 2) # 保留两位小数
    elif market_type in ('star', 'chinext'):
        # 科创板/创业板: ±20%
        return round(prev_close * 1.20, 2)
    elif market_type == 'bse':
        # 北交所: ±30%
        return round(prev_close * 1.30, 2)
    else:
        logger.warning(f"无法识别的股票代码 {stock_code}，无法计算涨停价。")
        return None

def calculate_lower_limit(stock_code, prev_close, stock_name):
    """
    根据股票代码、前收盘价和股票名称计算跌停价格。

     Args:
        stock_code (str): 股票代码 (纯数字部分，如 '600000').
        prev_close (float): 前一交易日收盘价.
        stock_name (str): 股票名称 (用于判断ST).

    Returns:
        float or None: 跌停价格，如果无法确定则返回 None.
    """
    if not isinstance(prev_close, (int, float)) or prev_close <= 0:
        logger.warning(f"无效的前收盘价: {prev_close} for stock {stock_code}")
        return None

    if stock_name is None:
        return None

    market_type = get_stock_market_type(stock_code)

    if market_type == 'main':
        # 主板: 正常 ±10%, ST ±5%
        limit_factor = 0.95 if 'ST' in stock_name or '*ST' in stock_name else 0.90
        return round(prev_close * limit_factor, 2) # 保留两位小数
    elif market_type in ('star', 'chinext'):
        # 科创板/创业板: ±20%
        return round(prev_close * 0.80, 2)
    elif market_type == 'bse':
         # 北交所: ±30%
        return round(prev_close * 0.70, 2)
    else:
        logger.warning(f"无法识别的股票代码 {stock_code}，无法计算跌停价。")
        return None

def get_stock_market_type(stock_code):
    """
    根据股票代码前缀判断市场和板块类型。

    返回: 'main', 'star', 'chinext', 'bse', or None
    """
    # 主板 (上海 + 深圳 A/B股)
    if stock_code.startswith(("600", "601", "603", "605", "900", "000", "001", "002", "003", "200", "201")):
        return 'main'
    # 科创板 (上海)
    elif stock_code.startswith(("688", "689")):
        return 'star'
    # 创业板 (深圳)
    elif stock_code.startswith(("300", "301", "302")):
        return 'chinext'
    # 北交所
    elif stock_code.startswith(("43", "83", "87","920")):
        return 'bse'
    else:
        return None

def ts_is_trading_day(date):
    """
    判断传入的日期是否为股票交易日

    参数:
    date: 日期字符串，格式为 "YYYY-MM-DD"

    返回:
    bool: 如果是交易日返回 True，否则返回 False
    """
    try:
        # 获取指定日期的交易日历信息
        cal_df = ts.pro_api().query('trade_cal',
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

def get_previous_month_dates(date_str):
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


def get_tushare_suffix(code):
    code = code.split('.')[0]
    if code.startswith(("600", "601", "603", "688", "689", "605", "900")):
        return f"{code}.SH"  # 上海证券交易所
    elif code.startswith(("000", "001", "300", "200", "002", "301", "201", "003", "302")):
        return f"{code}.SZ"  # 深圳证券交易所
    elif code.startswith(("43", "83", "87", "920")):
        return f"{code}.BJ"  # 北京证券交易所
    else:
        return "UNKNOWN"