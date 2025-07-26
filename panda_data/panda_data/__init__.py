# panda_data/__init__.py
import logging
from typing import Optional, List, Union

import pandas as pd

from panda_common.config import get_config
from panda_data.factor.factor_reader import FactorReader
from panda_data.market_data.market_data_reader import MarketDataReader
from panda_data.market_data.market_stock_cn_minute_reader import MarketStockCnMinReaderV3

_config = None
_factor = None
_market_data = None
_market_min_data: MarketStockCnMinReaderV3 = None


def init(configPath: Optional[str] = None) -> None:
    """
    Initialize the panda_data package with configuration

    Args:
        config_path: Path to the config file. If None, will use default config from panda_common.config
    """
    global _config, _factor, _market_data, _market_min_data

    try:
        # 使用panda_common中的配置
        _config = get_config()

        if not _config:
            raise RuntimeError("Failed to load configuration from panda_common")

        _factor = FactorReader(_config)
        _market_data = MarketDataReader(_config)
        _market_min_data = MarketStockCnMinReaderV3(_config)
    except Exception as e:
        raise RuntimeError(f"Failed to initialize panda_data: {str(e)}")


def get_all_symbols() -> pd.DataFrame:
    if _market_min_data is None:
        raise RuntimeError("Please call init() before using any functions")
    return _market_min_data.get_all_symbols()


def get_factor(
        factors: Union[str, List[str]],
        start_date: str,
        end_date: str,
        symbols: Optional[Union[str, List[str]]] = None,
        index_component: Optional[str] = None,
        type: Optional[str] = 'stock'
) -> Optional[pd.DataFrame]:
    """
    Get factor data for given symbols and date range

    Args:
        factors: List of factor names to retrieve or single factor name
        start_date: Start date in YYYYMMDD format
        end_date: End date in YYYYMMDD format
        symbols: Optional list of symbols or single symbol. If None, returns all symbols

    Returns:
        pandas DataFrame with factor data, or None if no data found
    """
    if _factor is None:
        raise RuntimeError("Please call init() before using any functions")

    return _factor.get_factor(symbols, factors, start_date, end_date, index_component, type)


def get_custom_factor(
        factor_logger: logging.Logger,
        user_id: int,
        factor_name: str,
        start_date: str,
        end_date: str,
        symbol_type: Optional[str] = 'stock'
) -> Optional[pd.DataFrame]:
    """
    Get factor data for given symbols and date range

    Args:
        factors: List of factor names to retrieve or single factor name
        start_date: Start date in YYYYMMDD format
        end_date: End date in YYYYMMDD format
        symbols: Optional list of symbols or single symbol. If None, returns all symbols

    Returns:
        pandas DataFrame with factor data, or None if no data found
    """
    if _factor is None:
        raise RuntimeError("Please call init() before using any functions")

    return _factor.get_custom_factor(factor_logger, user_id, factor_name, start_date, end_date, symbol_type)

def get_factor_by_name(factor_name, start_date, end_date):
    if _factor is None:
        raise RuntimeError("Please call init() before using any functions")
    return _factor.get_factor_by_name(factor_name, start_date, end_date)


"""获取所有股票代码"""


def get_stock_instruments() -> pd.DataFrame:
    stocks = _market_min_data.get_stock_instruments()
    return pd.DataFrame(stocks)


def get_market_min_data(
        start_date: str,
        end_date: str,
        symbol: Optional[str] = None,
        fields: Optional[Union[str, List[str]]] = None
) -> Optional[pd.DataFrame]:
    """
    Get market data for given symbols and date range

    Args:
        start_date: Start date in YYYYMMDD format
        end_date: End date in YYYYMMDD format
        symbols: Optional list of symbols or single symbol. If None, returns all symbols
        fields: Optional list of fields to retrieve (e.g., ['open', 'close', 'volume']).
               If None, returns all available fields

    Returns:
        pandas DataFrame with market data, or None if no data found
    """
    if _market_min_data is None:
        raise RuntimeError("Please call init() before using any functions")

    return _market_min_data.get_data(
        symbol=symbol,
        start_date=start_date,
        end_date=end_date,
        fields=fields
    )


def get_market_data(
        start_date: str,
        end_date: str,
        indicator="000985",
        st=True,
        symbols: Optional[Union[str, List[str]]] = None,
        fields: Optional[Union[str, List[str]]] = None
) -> Optional[pd.DataFrame]:
    """
    Get market data for given symbols and date range

    Args:
        start_date: Start date in YYYYMMDD format
        end_date: End date in YYYYMMDD format
        symbols: Optional list of symbols or single symbol. If None, returns all symbols
        fields: Optional list of fields to retrieve (e.g., ['open', 'close', 'volume']).
               If None, returns all available fields

    Returns:
        pandas DataFrame with market data, or None if no data found
    """
    if _market_data is None:
        raise RuntimeError("Please call init() before using any functions")

    return _market_data.get_market_data(
        symbols=symbols,
        start_date=start_date,
        end_date=end_date,
        indicator=indicator,
        st=st,
        fields=fields
    )


def get_available_market_fields() -> List[str]:
    """
    Get all available fields in the stock_market collection

    Returns:
        List of available field names
    """
    if _market_data is None:
        raise RuntimeError("Please call init() before using any functions")

    return _market_data.get_available_fields()

# Add more public functions as needed