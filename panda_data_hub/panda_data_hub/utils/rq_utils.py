import rqdatac
from panda_common.logger_config import logger

def rq_is_trading_day(date):
    try:
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

def get_index_components(start_date, end_date):
    try:
        # 沪深300
        hs300_components = rqdatac.index_components('000300.XSHG', start_date = start_date, end_date = end_date)
        # 中证500
        zz500_components = rqdatac.index_components('000905.XSHG', start_date = start_date, end_date = end_date)
        # 中证1000
        zz1000_components = rqdatac.index_components('000852.XSHG', start_date = start_date, end_date = end_date)

        return hs300_components,zz500_components,zz1000_components
    except Exception as e:
        logger.error(f"Error getting index components: {str(e)}")

def get_ricequant_suffix(code):
    code = code.split('.')[0]
    if code.startswith(("600", "601", "603", "688", "689", "605", "900")):
        return f"{code}.XSHG"  # 上海证券交易所
    elif code.startswith(("000", "001", "300", "200", "002", "301", "201", "003", "302")):
        return f"{code}.XSHE"  # 深圳证券交易所
    elif code.startswith(("43", "83", "87", "920")):
        return f"{code}.BJSE"  # 北京证券交易所
    else:
        return "UNKNOWN"
