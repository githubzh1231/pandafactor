import pandas as pd
import numpy as np
import os
import logging
import statsmodels.api as sm
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
from scipy.stats import norm
from scipy.stats import ttest_ind
from IPython.display import display

import panda_data


# def cal_hfq(df:pd.DataFrame) -> pd.DataFrame:
#     """
#     # 计算后复权开盘价、收盘价和1/3/5/10/20未来的回报率
#     :param df:待计算的pd.DataFrame
#     """
#     df = df.sort_values(by='date')
#     df['pct'] = df['close'] / df['prev_close'] - 1 # 隔日收益率
#     df['div_factors'] = (1 + df['pct']).cumprod()   # 复权因子
#     df.head(1)['div_factors'] = 1
#     df['hfq_open'] = df.iloc[0]['open'] * df['div_factors'] / df.iloc[0]['div_factors']   # 后复权开盘价
#     #df['hfq_close'] = df.iloc[0]['close'] * df['div_factors'] / df.iloc[0]['div_factors']   # 后复权收盘价
#     df['1day_return'] = df['hfq_open'].shift(-2) / df['hfq_open'].shift(-1) - 1   # 1日回报率/日频回报率
#     df['3day_return'] = df['hfq_open'].shift(-4) / df['hfq_open'].shift(-1) - 1  # 3日回报率
#     df['5day_return'] = df['hfq_open'].shift(-6) / df['hfq_open'].shift(-1) - 1  # 5日/周频回报率
#     df['10day_return'] = df['hfq_open'].shift(-11) / df['hfq_open'].shift(-1) - 1  # 10日/双周频回报率
#     df['20day_return'] = df['hfq_open'].shift(-21) / df['hfq_open'].shift(-1) - 1  # 20日/月度回报率
#     df.pop('prev_close')
#     df.pop('div_factors')
#     return df
def cal_hfq(df: pd.DataFrame) -> pd.DataFrame:
    """
    # Calculate backward adjusted prices and future returns for 1/3/5/10/20/30 days
    :param df: DataFrame to be processed
    """
    df = df.sort_values(by='date')
    df['pct'] = df['close'] / df['pre_close'] - 1  # Daily return
    df['div_factors'] = (1 + df['pct']).cumprod()  # Adjustment factor
    df.at[df.index[0], 'div_factors'] = 1
    df['hfq_open'] = df.iloc[0]['open'] * df['div_factors'] / df.iloc[0]['div_factors']  # Backward adjusted open price
    df['1day_return'] = df['hfq_open'].shift(-2) / df['hfq_open'].shift(-1) - 1  # 1-day return/daily return
    df['3day_return'] = df['hfq_open'].shift(-4) / df['hfq_open'].shift(-1) - 1  # 3-day return
    df['5day_return'] = df['hfq_open'].shift(-6) / df['hfq_open'].shift(-1) - 1  # 5-day/weekly return
    df['10day_return'] = df['hfq_open'].shift(-11) / df['hfq_open'].shift(-1) - 1  # 10-day/biweekly return
    df['20day_return'] = df['hfq_open'].shift(-21) / df['hfq_open'].shift(-1) - 1  # 20-day/monthly return
    df['30day_return'] = df['hfq_open'].shift(-31) / df['hfq_open'].shift(-1) - 1  # 30-day return
    df.pop('pct')
    df.pop('pre_close')
    df.pop('div_factors')
    return df


def cal_hfq2(df: pd.DataFrame) -> pd.DataFrame:
    """
    # Calculate backward adjusted OHLC and future returns for 1/5/10/20 days
    :param df: DataFrame to be processed
    """
    df = df.sort_values(by='trade_date')
    df['pct'] = df['close'] / df['pre_close'] - 1  # Daily return
    df['div_factors'] = (1 + df['pct']).cumprod()  # Adjustment factor
    df.head(1)['div_factors'] = 1
    df['hfq_open'] = df.iloc[0]['open'] * df['div_factors'] / df.iloc[0]['div_factors']  # Backward adjusted open price
    df['hfq_high'] = df.iloc[0]['high'] * df['div_factors'] / df.iloc[0]['div_factors']  # Backward adjusted high price
    df['hfq_low'] = df.iloc[0]['low'] * df['div_factors'] / df.iloc[0]['div_factors']  # Backward adjusted low price
    df['hfq_close'] = df.iloc[0]['close'] * df['div_factors'] / df.iloc[0][
        'div_factors']  # Backward adjusted close price
    df['1day_return'] = df['hfq_open'].shift(-2) / df['hfq_open'].shift(-1) - 1  # 1-day return/daily return
    df['5day_return'] = df['hfq_open'].shift(-6) / df['hfq_open'].shift(-1) - 1  # 5-day/weekly return
    df['10day_return'] = df['hfq_open'].shift(-11) / df['hfq_open'].shift(-1) - 1  # 10-day/biweekly return
    df['20day_return'] = df['hfq_open'].shift(-21) / df['hfq_open'].shift(-1) - 1  # 20-day/monthly return
    # df.pop('pre_close')
    df.pop('div_factors')
    return df


def cal_pct_lag(df: pd.DataFrame) -> pd.DataFrame:
    """
    # Calculate stock returns lagged by 1-20 days
    :param df: DataFrame to be processed
    """
    for i in range(0, 21):
        df[f'returns_lag{i}'] = df.groupby('symbol')['1day_return'].transform(lambda x: x.shift(-i))
    return df


def str_round(number: float, decimal_places: int, percentage: bool = False) -> str:
    """
    # Custom rounding method with higher precision
    :param number: Number to be processed
    :param decimal_places: Number of decimal places to keep
    :param percentage: Whether to display as percentage
    """
    if pd.notna(number):
        multiplier = 10 ** decimal_places
        rounded_number = int(number * multiplier + 0.5) / multiplier  # Use integer method for rounding
        # If percentage display is needed
        if percentage:
            rounded_number *= 100
            format_string = "{:." + str(decimal_places - 2) + "f}%"
        else:
            format_string = "{:." + str(decimal_places) + "f}"
        # Use string formatting to truncate decimals
        result_str = format_string.format(rounded_number)
        return result_str
    else:
        return ""  # Return empty string for NaN values


def clean_k_data(df_k_data: pd.DataFrame) -> pd.DataFrame:
    """
    清洗K线数据，移除不必要的列，并标记无法交易的数据点。

    参数:
    df_k_data (pd.DataFrame): 包含K线数据的DataFrame，需包含以下列：
                              'high', 'low', 'limit_up', 'limit_down',
                              'total_turnover', 'volume', 'num_trades'.

    返回:
    pd.DataFrame: 清洗后的DataFrame，包含标记无法交易的列 'unable_trade'。
    """

    # 标记无法交易的数据点（一字涨停或跌停）
    df_k_data['unable_trade'] = np.where(
        (df_k_data['high'] == df_k_data['low']) &  # 最高价等于最低价
        ((df_k_data['high'] == df_k_data['limit_up']) | (df_k_data['low'] == df_k_data['limit_down'])),  # 并且是涨停或跌停
        1,  # 满足条件则标记为1（无法交易）
        0  # 否则标记为0（可以交易）
    )

    # 移除不再需要的列
    # columns_to_drop = ['limit_up', 'limit_down', 'high', 'low', 'total_turnover', 'volume', 'num_trades']
    columns_to_drop = ['limit_up', 'limit_down', 'high', 'low', 'volume']
    df_k_data = df_k_data.drop(columns=columns_to_drop)

    return df_k_data


def read_kdata(start_date: str, end_date: str, field: list = []) -> pd.DataFrame:
    """
    # Read K-line data
    :param start_date: Start date of data
    :param end_date: End date of data (inclusive)
    :param field: Fields to keep (['trade_date'(default),'ts_code'(default),'name'(default),'open'(default),'high','low','close'(default),'pre_close'(default),
    'vol','amount','turnover_rate','limit_up','limit_down','unable_trade'(default),'industry'(default),'total_mv'(default),'circ_mv'])
    """

    df_list = []
    folder_path = "D:\\quant\\project\\Backtesting\\single-factor\\stock_data\\data_daily_kline"
    for path in os.listdir(folder_path):
        date = path[:-4]
        if start_date <= date <= end_date:
            df_temp = pd.read_csv(f'{folder_path}\\{path}')
            df_temp['trade_date'] = date
            df_list.append(df_temp)

    df_kdata = pd.concat(df_list)
    df_kdata['trade_date'] = pd.to_datetime(df_kdata['trade_date'], format='%Y-%m-%d')
    df_kdata = df_kdata[
        ['trade_date', 'ts_code', 'name', 'open', 'close', 'pre_close', 'unable_trade', 'industry', 'total_mv'] + field]

    return df_kdata


def read_kdata_min(start_time: str, end_time: str, code_list: list = []) -> pd.DataFrame:
    """
    # Read 1-minute K-line data
    :param start_date: Start date of data
    :param end_date: End date of data (inclusive)
    :param code_list: List of stock codes to read
    """

    df_list = []
    folder_path = "D:\\quant\\project\\Backtesting\\single-factor\\stock_data\\data_1min_kline\\"
    for code in code_list:
        path = folder_path + code + '.csv'
        temp = pd.read_csv(path)
        temp['ts_code'] = code
        df_list.append(temp)
    df = pd.concat(df_list)

    df = df[(df['trade_time'] >= start_time) & (df['trade_time'] <= end_time)]

    df['trade_time'] = pd.to_datetime(df['trade_time'], format='%Y%m%d %H:%M:%S')

    return df


def get_all_stock_code() -> list:
    """
    # Get a list of all stocks that have been listed
    """
    path_list = []
    folder_path = "D:\\quant\\project\\Backtesting\\single-factor\\stock_data\\data_1min_kline"
    for path in os.listdir(folder_path):
        path_list.append(path)
    path_list = [i[:-4] for i in path_list]
    return path_list


def read_capital_flow(start_date: str, end_date: str) -> pd.DataFrame:
    """
    # Read capital flow data
    :param start_date: Start date of data
    :param end_date: End date of data (inclusive)
    # Field explanation:
    buy_sm_vol       Small order buy volume (lots)
    buy_sm_amount    Small order buy amount (10,000 yuan)
    sell_sm_vol      Small order sell volume (lots)
    sell_sm_amount   Small order sell amount (10,000 yuan)
    buy_md_vol       Medium order buy volume (lots)
    buy_md_amount    Medium order buy amount (10,000 yuan)
    sell_md_vol      Medium order sell volume (lots)
    sell_md_amount   Medium order sell amount (10,000 yuan)
    buy_lg_vol       Large order buy volume (lots)
    buy_lg_amount    Large order buy amount (10,000 yuan)
    sell_lg_vol      Large order sell volume (lots)
    sell_lg_amount   Large order sell amount (10,000 yuan)
    buy_elg_vol      Extra large order buy volume (lots)
    buy_elg_amount   Extra large order buy amount (10,000 yuan)
    sell_elg_vol     Extra large order sell volume (lots)
    sell_elg_amount  Extra large order sell amount (10,000 yuan)
    net_mf_vol       Net inflow volume (lots)
    net_mf_amount    Net inflow amount (10,000 yuan)
    """

    df_list = []
    folder_path = "D:\\quant\\project\\Backtesting\\single-factor\\stock_data\\data_capital_flow"
    for path in os.listdir(folder_path):
        date = path[:-4]
        if start_date <= date <= end_date:
            df_temp = pd.read_csv(f'{folder_path}\\{path}')
            df_temp['trade_date'] = date
            df_list.append(df_temp)

    df_capital_flow = pd.concat(df_list)
    df_capital_flow['trade_date'] = pd.to_datetime(df_capital_flow['trade_date'], format='%Y-%m-%d')

    return df_capital_flow


def read_north(start_date: str, end_date: str) -> pd.DataFrame:
    """
    # Read northbound capital data
    :param start_date: Start date of data
    :param end_date: End date of data (inclusive)
    # Field explanation:
    code        Original code
    trade_date  Trading date
    ts_code     TS code
    name        Stock name (traditional Chinese)
    vol         Holding quantity (shares)
    ratio       Holding ratio (%), percentage of issued shares
    exchange    Type: SH (Shanghai Connect), SZ (Shenzhen Connect), HK (Hong Kong Connect)
    """

    df_list = []
    folder_path = "D:\\quant\\project\\Backtesting\\single-factor\\stock_data\\data_north"
    for path in os.listdir(folder_path):
        date = path[:-4]
        if start_date <= date <= end_date:
            df_temp = pd.read_csv(f'{folder_path}\\{path}')
            df_temp['trade_date'] = date
            df_list.append(df_temp)

    df_north = pd.concat(df_list)
    df_north['trade_date'] = pd.to_datetime(df_north['trade_date'], format='%Y-%m-%d')

    return df_north


def read_margin_trading(start_date: str, end_date: str) -> pd.DataFrame:
    """
    # Read margin trading data
    :param start_date: Start date of data
    :param end_date: End date of data (inclusive)
    # Field explanation:
    ts_code      Stock code
    rzye         Margin balance (yuan)
    rqye         Short selling balance (yuan)
    rzmre        Margin purchase amount (yuan)
    rqyl         Short selling volume (shares)
    rzche        Margin repayment amount (yuan)
    rqchl        Short covering volume (shares)
    rqmcl        Short selling volume (shares, units, lots)
    rzrqye       Margin trading balance (yuan)
    Today's margin balance (yuan) = Previous day's margin balance + Today's margin purchase - Today's margin repayment
    Today's short selling volume (shares) = Previous day's short selling volume + Today's short selling - Today's short buying - Today's short covering
    Today's short selling balance (yuan) = Today's short selling volume × Today's closing price
    Today's margin trading balance (yuan) = Today's margin balance + Today's short selling balance

    Unit explanation: shares (for stocks), units (for funds), lots (for bonds)
    """

    df_list = []
    folder_path = "D:\\quant\\project\\Backtesting\\single-factor\\stock_data\\data_margin_trading"
    for path in os.listdir(folder_path):
        date = path[:-4]
        if start_date <= date <= end_date:
            df_temp = pd.read_csv(f'{folder_path}\\{path}')
            df_temp['trade_date'] = date
            df_list.append(df_temp)

    df_margin_trading = pd.concat(df_list)
    df_margin_trading['trade_date'] = pd.to_datetime(df_margin_trading['trade_date'], format='%Y-%m-%d')

    return df_margin_trading


def read_daily_basic(start_date: str, end_date: str) -> pd.DataFrame:
    """
    # Read daily indicator data
    :param start_date: Start date of data
    :param end_date: End date of data (inclusive)
    # Field explanation:
    ts_code           TS stock code
    trade_date        Trading date
    close             Closing price of the day
    turnover_rate     Turnover rate (%)
    turnover_rate_f   Turnover rate (free float)
    volume_ratio      Volume ratio
    pe                Price-to-earnings ratio (total market value/net profit, empty for loss-making companies)
    pe_ttm            PE TTM (empty for loss-making companies)
    pb                Price-to-book ratio (total market value/net assets)
    ps                Price-to-sales ratio
    ps_ttm            Price-to-sales ratio (TTM)
    dv_ratio          Dividend yield (%)
    dv_ttm            Dividend yield TTM (%)
    total_share       Total shares (10,000 shares)
    float_share       Tradable shares (10,000 shares)
    free_share        Free-float shares (10,000)
    total_mv          Total market value (10,000 yuan)
    circ_mv           Circulation market value (10,000 yuan)
    """

    df_list = []
    folder_path = "D:\\quant\\project\\Backtesting\\single-factor\\stock_data\\data_daily_basic"
    for path in os.listdir(folder_path):
        date = path[:-4]
        if start_date <= date <= end_date:
            df_temp = pd.read_csv(f'{folder_path}\\{path}')
            df_temp['trade_date'] = date
            df_list.append(df_temp)

    df_margin_trading = pd.concat(df_list)
    df_margin_trading['trade_date'] = pd.to_datetime(df_margin_trading['trade_date'], format='%Y-%m-%d')

    return df_margin_trading


def read_factor(factor_name_list: list, start_date: str, end_date: str) -> pd.DataFrame:
    """
    # Read multiple factor data and merge them
    :param factor_name_list: List of factor names
    :param start_date: Start date of data
    :param end_date: End date of data (inclusive)
    """

    df_factor_merged = None
    factor_path_base = 'D:\\quant\\project\\Backtesting\\single-factor\\factor_lib\\'

    for factor_name in factor_name_list:
        df_list = []
        factor_path = factor_path_base + factor_name + '\\csv'
        for path in os.listdir(factor_path):
            date = path[:-4]
            if start_date <= date <= end_date:
                df_temp = pd.read_csv(f'{factor_path}\\{path}')
                df_temp['trade_date'] = date
                df_list.append(df_temp)
        df_factor = pd.concat(df_list)
        df_factor['trade_date'] = pd.to_datetime(df_factor['trade_date'], format='%Y-%m-%d')

        if df_factor_merged is None:
            df_factor_merged = df_factor
        else:
            # Merge by trading date, can adjust merging method as needed
            df_factor_merged = pd.merge(df_factor_merged, df_factor, on=['trade_date', 'ts_code'], how='outer')

    if df_factor_merged is None:
        return pd.DataFrame()  # Return empty DataFrame in case of None
    return df_factor_merged


def read_jtfactor(path: str) -> pd.DataFrame:
    """
    # Read multiple factor data and merge them
    :param path: Network path for factor file
    """
    df_factor = pd.read_parquet(path)
    df_factor['ts_code'] = df_factor['order_book_id'].apply(change_code)
    df_factor.insert(0, 'trade_date', df_factor.pop('date'))
    df_factor.pop('order_book_id')
    return df_factor


def read_barra(start_date: str, end_date: str) -> pd.DataFrame:
    """
    # Read Barra factor data
    :param start_date: Start date of data
    :param end_date: End date of data (inclusive)
    """
    path_barra = "D:\\quant\\project\\Backtesting\\single-factor\\stock_data\\data_barra"
    df_list = []
    for path in os.listdir(path_barra):
        date = path[:-4]
        if start_date <= date <= end_date:
            df_list.append(pd.read_csv(f'{path_barra}\\{path}'))
    df_barra = pd.concat(df_list)
    df_barra['trade_date'] = pd.to_datetime(df_barra['trade_date'], format='%Y-%m-%d')
    df_barra.rename(columns={'book_to_price_ratio': 'BP Value Factor', 'leverage': 'LEVERAGE Factor',
                             'liquidity': 'LIQUIDTY Factor', 'beta': 'BETA Market Factor', 'growth': 'GROWTH Factor',
                             'residual_volatility': 'RESVOL Volatility Factor',
                             'non_linear_size': 'SIZENL Non-linear Size Factor',
                             'earnings_yield': 'EARNYILD Earnings Factor', 'momentum': 'MOMENTUM Factor',
                             'size': 'SIZE Market Cap Factor'}, inplace=True)
    return df_barra


def cal_barra_corr(df_factor: pd.DataFrame) -> pd.DataFrame:
    """
    # Calculate Barra factor correlation, returns correlation matrix
    :param df_factor: DataFrame with stock factor columns
    """
    start_date = df_factor['trade_date'].astype(str).unique().min()
    end_date = df_factor['trade_date'].astype(str).unique().max()
    factor_list = df_factor.columns.tolist()[2:]
    df_barra = read_barra(start_date, end_date)
    df_merged = pd.merge(df_factor, df_barra, on=['ts_code', 'trade_date'], how='inner')
    barra_factors = ['BP Value Factor', 'LEVERAGE Factor', 'LIQUIDTY Factor', 'BETA Market Factor', 'GROWTH Factor',
                     'RESVOL Volatility Factor', 'SIZENL Non-linear Size Factor', 'EARNYILD Earnings Factor',
                     'MOMENTUM Factor', 'SIZE Market Cap Factor']
    correlation_matrix = df_merged.corr(numeric_only=True).loc[factor_list, barra_factors]

    return correlation_matrix.T


def ext_out_mad(group: pd.DataFrame, factor_list: list) -> pd.DataFrame:
    """
    # Median absolute deviation outlier removal
    :param group: Daily factor data DataFrame
    :param factor_list: List of factor names to process
    """
    for f in factor_list:
        factor = group[f]
        median = factor.median()
        mad = (factor - median).abs().median()
        edge_up = median + 3 * mad
        edge_low = median - 3 * mad
        factor.clip(lower=edge_low, upper=edge_up, inplace=True)
        group[f] = factor
    return group


# def ext_out_3std(group:pd.DataFrame,factor_list:list) -> pd.DataFrame:
#     """
#     # 3-sigma outlier removal
#     :param group: Daily factor data DataFrame
#     :param factor_list: List of factor names to process
#     """
#     for f in factor_list:
#         factor = group[f]
#         edge_up = factor.mean() + 3 * factor.std()
#         edge_low = factor.mean() - 3 * factor.std()
#         factor.clip(lower=edge_low, upper=edge_up, inplace=True)
#         group[f] = factor
#     return group
def ext_out_3std(group: pd.DataFrame, factor_name: str, noise_std: float = 1e-10,
                 ) -> pd.DataFrame:
    """
    # 3-sigma 异常值移除并添加噪音确保唯一的分箱边界
    :param group: 日度因子数据 DataFrame
    :param factor_name: 需要处理的因子名称
    :param noise_std: 添加噪音的标准差，默认为 1e-10
    :param group_cnt: 分箱的数量，默认为 5
    """
    # 获取指定因子的列
    factor = group[factor_name]

    # 添加噪音到因子列，噪音是均值为 0，标准差为 noise_std 的正态分布
    noise = np.random.normal(0, noise_std, size=len(factor))
    factor += noise  # 将噪音加到因子列

    # 确保因子列是浮动类型，避免 dtype 不兼容
    factor = factor.astype(float)

    # 计算 3-sigma 范围的上下边界
    edge_up = factor.mean() + 3 * factor.std()
    edge_low = factor.mean() - 3 * factor.std()

    # 使用 clip 限制因子的上下边界，去除异常值
    factor.clip(lower=edge_low, upper=edge_up, inplace=True)

    # 将因子列更新回去
    group[factor_name] = factor

    return group


def ext_out_3std_list(group: pd.DataFrame, factor_list: list, noise_std: float = 1e-10,
                      ) -> pd.DataFrame:
    """
    # 3-sigma 异常值移除并添加噪音确保唯一的分箱边界
    :param group: 日度因子数据 DataFrame
    :param factor_name: 需要处理的因子名称
    :param noise_std: 添加噪音的标准差，默认为 1e-10
    :param group_cnt: 分箱的数量，默认为 5
    """
    for f in factor_list:
        # 获取指定因子的列
        factor = group[f]

        # 添加噪音到因子列，噪音是均值为 0，标准差为 noise_std 的正态分布
        noise = np.random.normal(0, noise_std, size=len(factor))
        factor += noise  # 将噪音加到因子列

        # 确保因子列是浮动类型，避免 dtype 不兼容
        factor = factor.astype(float)

        # 计算 3-sigma 范围的上下边界
        edge_up = factor.mean() + 3 * factor.std()
        edge_low = factor.mean() - 3 * factor.std()

        # 使用 clip 限制因子的上下边界，去除异常值
        factor.clip(lower=edge_low, upper=edge_up, inplace=True)

        # 将因子列更新回去
        group[f] = factor

    return group


def market_value_neutralization(group: pd.DataFrame, factor_list: list) -> pd.DataFrame:
    """
    # Market cap logarithm neutralization
    :param group: Daily factor data DataFrame
    :param factor_list: List of factor names to process
    """
    for f in factor_list:
        X = group['total_mv'].apply(np.log)
        y = group[f]
        X = sm.add_constant(X)
        model = sm.OLS(y, X).fit()
        group[f] = model.resid
    return group


def industry_neutralization(df: pd.DataFrame, factor_list: list) -> pd.DataFrame:
    """
    # Industry neutralization
    :param df: DataFrame containing factor columns and industry information
    :param factor_list: List of factor names to process
    :return: DataFrame after neutralization processing
    """
    # Create industry dummy variables
    industry_dummies = pd.get_dummies(df['industry'], prefix='industry')
    df = pd.concat([df, industry_dummies], axis=1)

    # Apply industry neutralization to each factor
    for factor in factor_list:
        # Define internal function for regression analysis
        def industry_neutralization_per_factor(group):
            y = group[factor].values
            X = group[industry_dummies.columns].values
            X = sm.add_constant(X)
            model = sm.OLS(y, X).fit()
            group[factor] = model.resid
            return group

        # Apply neutralization processing
        df = df.groupby('trade_date', group_keys=False, observed=True).apply(industry_neutralization_per_factor)

    # Remove industry dummy variable columns
    df = df.drop(columns=industry_dummies.columns)
    return df


def z_score(group: pd.DataFrame, factor_list: list) -> pd.DataFrame:
    """
    # Z-score standardization
    :param group: Daily factor data DataFrame
    :param factor_list: List of factor names to process
    """
    for f in factor_list:
        factor = group[f]
        if factor.std() != 0:
            group[f] = (factor - factor.mean()) / factor.std()
        else:
            group[f] = np.nan
    return group


def barra_neutralization(df: pd.DataFrame, factor_list: list) -> pd.DataFrame:
    """
    # Barra factor neutralization
    :param df: DataFrame containing factor columns
    :param factor_list: List of factor names to process
    :return: Barra-neutralized results, returns only new factor columns with suffix '_del_barra'
    """
    start_date = df['trade_date'].astype(str).min()
    end_date = df['trade_date'].astype(str).max()
    df_barra = read_barra(start_date, end_date)
    df_merged = pd.merge(df, df_barra, on=['ts_code', 'trade_date'], how='inner')

    new_factor_list = []
    barra_factors = ['BP Value Factor', 'LEVERAGE Factor', 'LIQUIDTY Factor', 'BETA Market Factor', 'GROWTH Factor',
                     'RESVOL Volatility Factor', 'SIZENL Non-linear Size Factor', 'EARNYILD Earnings Factor',
                     'MOMENTUM Factor', 'SIZE Market Cap Factor']

    # Remove the influence of x factors on y factors, take the residuals of cross-sectional factors
    def del_factor_x(group):
        for f in factor_list:
            new_factor_name = f'{f}_del_barra'
            if new_factor_name not in new_factor_list:
                new_factor_list.append(new_factor_name)
            group[new_factor_name] = np.nan

            Y = group[f]
            for barra in barra_factors:
                X = group[barra]
                X = sm.add_constant(X)
                group[new_factor_name] = sm.OLS(Y, X).fit().resid
        return group

    df_merged = df_merged.groupby('trade_date', group_keys=False, observed=True).apply(del_factor_x)
    if df_merged is None:
        return pd.DataFrame()  # Return empty DataFrame in case of None
    return df_merged[['ts_code', 'trade_date'] + new_factor_list]


def clean_df(df: pd.DataFrame, factor_list: list) -> pd.DataFrame:
    """
    # Clean data (including removing ST stocks, delisted stocks, missing returns, missing factor values)
    :param group: Daily factor data DataFrame to be processed
    :param factor_list: List of factor names to process
    """
    df = df[(~df['name'].str.contains('ST')) & (~df['name'].str.contains('退'))]
    df = df[df[factor_list].notna().all(axis=1)]
    df = df[df['20day_return'].notna()]
    df = df.drop('name', axis=1)
    return df


def grouping_factor(df: pd.DataFrame, factor_name: str, group_cnt: int = 10, logger=None) -> tuple[
    pd.DataFrame, pd.DataFrame]:
    """
    # Create cross-sectional groups for factor data
    Groups the df containing factor values, records group numbers, removes stocks that cannot be traded due to limit up/down,
    and simultaneously records the average market return for each day
    :param df: Daily factor data DataFrame to be processed
    :param factor_name: Factor name to be processed
    :param group_cnt: Number of groups, default is 10, valid range 2-20
    :param logger: Logger instance, default is None
    :return: Returns a tuple (DataFrame with group numbers in a new column named '{factor_name}_group', DataFrame recording daily market average returns)
    """
    benchmark_pct = {}  # Store benchmark index daily returns {'date': ...}
    grouped_dfs = []  # For collecting processed groups

    # Validate if group count is in valid range
    if group_cnt < 2 or group_cnt > 20:
        if logger:
            logger.warning(f"Group count {group_cnt} is out of range (2-20), will use default value 10")
        else:
            print(f"Warning: Group count {group_cnt} is out of range (2-20), will use default value 10")
        group_cnt = 10

    for date, group in df.groupby('date'):
        benchmark_pct_child = {}
        benchmark_pct_child['1D_m'] = group[
            '1day_return'].mean()  # Calculate average return of all stocks for next period
        benchmark_pct_child['3D_m'] = group['3day_return'].mean()
        benchmark_pct_child['5D_m'] = group['5day_return'].mean()
        benchmark_pct_child['10D_m'] = group['10day_return'].mean()
        benchmark_pct_child['20D_m'] = group['20day_return'].mean()
        benchmark_pct_child['30D_m'] = group['30day_return'].mean()
        benchmark_pct[date] = benchmark_pct_child

        # Remove stocks that cannot be traded due to limit up/down
        group = group[group['unable_trade'] == 0]  # Remove untradable stocks (limit up/down)

        if group.empty:  # Check if DataFrame is empty
            continue

        # Create a new column named '{factor_name}_group' containing grouping information
        new_group = group.copy()

        if group[
            factor_name].dropna().nunique() < group_cnt:  # Check if the number of unique values after removing NaN is less than group_cnt
            if logger:
                logger.warning(f"Factor {factor_name},{date},group count less than {group_cnt}, will skip")
            else:
                print(f"Warning: Factor {factor_name},{date},group count less than {group_cnt}, will skip")
            continue

        # Use qcut for grouping and ensure the number of groups is correct
        try:

            # Add a small random noise to ensure unique bin edges
            noise = np.random.normal(0, 1e-10, size=group[factor_name].dropna().shape)
            noisy_values = group[factor_name].dropna().values + noise
            new_group[f'{factor_name}_group'] = pd.qcut(noisy_values, q=group_cnt, labels=range(1, group_cnt + 1))
            # new_group[f'{factor_name}_group'] = pd.qcut(group[factor_name].dropna(), q=group_cnt, labels=range(1, group_cnt+1))
        except ValueError as e:
            if logger:
                logger.error(f"{factor_name},{date},grouping failed: {str(e)}")
            else:
                print(f"Error: {factor_name},{date},grouping failed: {str(e)}")
            continue

        grouped_dfs.append(new_group)

    # Merge all processed groups
    if grouped_dfs:
        df_cuted = pd.concat(grouped_dfs)
    else:
        df_cuted = pd.DataFrame()  # If there's no valid data, return an empty DataFrame

    # Convert benchmark index returns to DataFrame
    df_benchmark = pd.DataFrame(benchmark_pct).T

    return df_cuted, df_benchmark


def grouping_factor_list(df: pd.DataFrame, factor_list: list, group_cnt: int = 10, logger=None) -> tuple[
    pd.DataFrame, pd.DataFrame]:
    """
    # Create cross-sectional groups for factor data
    Groups the df containing factor values, records group numbers, removes stocks that cannot be traded due to limit up/down,
    and simultaneously records the average market return for each day
    :param df: Daily factor data DataFrame to be processed
    :param factor_name: Factor name to be processed
    :param group_cnt: Number of groups, default is 10, valid range 2-20
    :param logger: Logger instance, default is None
    :return: Returns a tuple (DataFrame with group numbers in a new column named '{factor_name}_group', DataFrame recording daily market average returns)
    """
    benchmark_pct = {}  # Store benchmark index daily returns {'date': ...}
    grouped_dfs = []  # For collecting processed groups

    # Validate if group count is in valid range
    if group_cnt < 2 or group_cnt > 20:
        if logger:
            logger.warning(f"Group count {group_cnt} is out of range (2-20), will use default value 10")
        else:
            print(f"Warning: Group count {group_cnt} is out of range (2-20), will use default value 10")
        group_cnt = 10

    for date, group in df.groupby('date'):
        benchmark_pct_child = {}
        benchmark_pct_child['1D_m'] = group[
            '1day_return'].mean()  # Calculate average return of all stocks for next period
        benchmark_pct_child['3D_m'] = group['3day_return'].mean()
        benchmark_pct_child['5D_m'] = group['5day_return'].mean()
        benchmark_pct_child['10D_m'] = group['10day_return'].mean()
        benchmark_pct_child['20D_m'] = group['20day_return'].mean()
        benchmark_pct_child['30D_m'] = group['30day_return'].mean()
        benchmark_pct[date] = benchmark_pct_child

        # Remove stocks that cannot be traded due to limit up/down
        group = group[group['unable_trade'] == 0]  # Remove untradable stocks (limit up/down)

        if group.empty:  # Check if DataFrame is empty
            continue

        # Create a new column named '{factor_name}_group' containing grouping information
        new_group = group.copy()
        for f in factor_list:
            new_group[f'{f}_group'] = np.nan
        for f in factor_list:

            if group[f].dropna().nunique() < group_cnt:  # 检查去掉NaN后的唯一值数量是否小于10
                print(f"Factor {f},{date},group count less than {group_cnt}, will skip")
                continue
            try:
                # 根据factor的值对group进行排序，并分为10个组
                noise = np.random.normal(0, 1e-10, size=group[f].dropna().shape)
                noisy_values = group[f].dropna().values + noise
                new_group[f'{f}_group'] = pd.qcut(noisy_values, q=group_cnt, labels=range(1, group_cnt + 1))
            except ValueError as e:
                if logger:
                    logger.error(f"{f},{date},grouping failed: {str(e)}")
                else:
                    print(f"Error: {f},{date},grouping failed: {str(e)}")
                continue
        # Use qcut for grouping and ensure the number of groups is correct

        grouped_dfs.append(new_group)

    # Merge all processed groups
    if grouped_dfs:
        df_cuted = pd.concat(grouped_dfs)
    else:
        df_cuted = pd.DataFrame()  # If there's no valid data, return an empty DataFrame

    # Convert benchmark index returns to DataFrame
    df_benchmark = pd.DataFrame(benchmark_pct).T

    return df_cuted, df_benchmark


def change_code(s):
    if s[-4:] == 'XSHE':
        return s[0:6] + '.SZ'
    elif s[-4:] == 'XSHG':
        return s[0:6] + '.SH'
    else:
        print('Unknown code!')
        return 0


if __name__ == '__main__':
    pass