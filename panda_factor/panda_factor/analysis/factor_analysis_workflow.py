import traceback
import warnings
from panda_factor.analysis.factor_func import *
from panda_factor.analysis.factor import factor
from panda_common.handlers.database_handler import DatabaseHandler
from panda_common.config import config
from panda_common.handlers.log_handler import get_factor_logger
from datetime import datetime
import uuid
import time
from typing import Sequence, Union


def cal_hfq_vectorized(
        df: pd.DataFrame,
        adjustment_cycles: Union[int, Sequence[int]]
) -> pd.DataFrame:
    if isinstance(adjustment_cycles, int):
        cycles = (adjustment_cycles,)
    else:
        cycles = tuple(sorted(set(adjustment_cycles)))

    # 1️⃣ 先整体按 symbol+date 排序，一次性完成
    df = df.sort_values(['symbol', 'date']).reset_index(drop=True)

    # 2️⃣ 日收益 & 复权因子
    df['pct'] = df['close'] / df['pre_close'] - 1.0
    df['div_factor'] = (1.0 + df['pct']).groupby(df['symbol']).cumprod()
    # 确保每个分组第一行为 1
    first_idx = df.groupby('symbol').head(1).index
    df.loc[first_idx, 'div_factor'] = 1.0

    # 3️⃣ 向后复权开盘价
    first_open = df.groupby('symbol')['open'].transform('first')
    first_div = df.groupby('symbol')['div_factor'].transform('first')
    df['hfq_open'] = first_open * df['div_factor'] / first_div

    # 4️⃣ 未来 1 日收益
    hfq_grp = df.groupby('symbol')['hfq_open']
    df['1day_return'] = hfq_grp.shift(-2) / hfq_grp.shift(-1) - 1.0

    # 5️⃣ 指定周期未来收益（一次循环，仍是向量化 shift）
    for n in cycles:
        df[f'{n}day_return'] = hfq_grp.shift(-(n + 1)) / hfq_grp.shift(-1) - 1.0

    # 6️⃣ 清理临时列
    df.drop(columns=['pct', 'pre_close', 'div_factor'], inplace=True)
    return df


#
# def cal_hfq(df:pd.DataFrame,adjustment_cycle:int) -> pd.DataFrame:
#     """
#     # Calculate backward adjusted prices and future returns for 1/3/5/10/20/30 days
#     :param df: DataFrame to be processed
#     """
#     df = df.sort_values(by='date')
#     df['pct'] = df['close'] / df['pre_close'] - 1 # Daily return
#     df['div_factors'] = (1 + df['pct']).cumprod()   # Adjustment factor
#     df.at[df.index[0], 'div_factors'] = 1
#     df['hfq_open'] = df.iloc[0]['open'] * df['div_factors'] / df.iloc[0]['div_factors']   # Backward adjusted open price
#     df[f'{adjustment_cycle}day_return']= df['hfq_open'].shift(-(adjustment_cycle+1)) / df['hfq_open'].shift(-1) - 1
#     df['1day_return'] = df['hfq_open'].shift(-2) / df['hfq_open'].shift(-1) - 1   # 1-day return/daily return
#     df.pop('pct')
#     df.pop('pre_close')
#     df.pop('div_factors')
#     return df

def grouping_factor(df: pd.DataFrame, factor_name: str, adjustment_cycle: int, group_cnt: int = 10) -> tuple[
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
        print(f"Warning: Group count {group_cnt} is out of range (2-20), will use default value 10")
        group_cnt = 10

    for date, group in df.groupby('date'):
        benchmark_pct_child = {}
        benchmark_pct_child[f'{adjustment_cycle}D_m'] = group[f'{adjustment_cycle}day_return'].mean()
        benchmark_pct[date] = benchmark_pct_child

        # Remove stocks that cannot be traded due to limit up/down
        group = group[group['unable_trade'] == 0]  # Remove untradable stocks (limit up/down)

        if group.empty:  # Check if DataFrame is empty
            continue

        # Create a new column named '{factor_name}_group' containing grouping information
        new_group = group.copy()

        if group[
            factor_name].dropna().nunique() < group_cnt:  # Check if the number of unique values after removing NaN is less than group_cnt

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


def cal_pct_lag(df: pd.DataFrame) -> pd.DataFrame:
    """
    Calculate stock returns lagged by 1-20 days for each symbol without using a for loop.
    :param df: DataFrame to be processed
    :return: DataFrame with additional columns for each lag
    """
    # 使用shift批量计算1到20天的滞后列
    lags = [df.groupby('symbol')['1day_return'].shift(-i) for i in range(1, 21)]

    # 将所有滞后列与原始DataFrame合并
    df = pd.concat([df] + lags, axis=1)

    # 给新的滞后列命名
    df.columns = list(df.columns[:-20]) + [f'returns_lag{i}' for i in range(1, 21)]

    return df


def factor_analysis_workflow(df_factor: pd.DataFrame, adjustment_cycle, group_number, factor_direction) -> None:
    warnings.filterwarnings("ignore")

    # Get task ID from the task
    _db_handler = DatabaseHandler(config)

    # 生成UUID
    task_id = uuid.uuid4().hex
    factor_id = uuid.uuid4().hex
    logger = get_factor_logger(
        task_id=task_id or "unknown",
        factor_id=factor_id or "unknown"
    )
    start_time = sorted(df_factor["date"].unique())[0]
    end_time = sorted(df_factor["date"].unique())[-1]
    # 生成task_id
    _db_handler.mongo_insert(
        "panda",
        "tasks",
        {
            "task_id": task_id,
            "task_type": "factor_analysis_workflow",
            "process_status": 1,  # Started
            "create_at": datetime.now().isoformat(),
        }
    )
    try:
        # Record analysis start
        logger.info(msg="====== Starting factor analysis ======")

        latest_date = df_factor['date'].max()
        logger.info(msg=f"Latest date: {latest_date}")

        # Initialize data
        panda_data.init()

        # Update status within the thread
        _db_handler.mongo_update(
            "panda",
            "tasks",
            {"task_id": task_id},
            {
                "process_status": 2,  # Started
                "updated_at": datetime.now().isoformat(),
            }
        )

        # Get K-line data
        logger.info(msg="1. Starting to fetch K-line data")
        try:
            df_k_data = panda_data.get_market_data(
                start_date=start_time,
                end_date=end_time
            )
            logger.info(msg=f"k-line data length: {len(df_k_data) if df_k_data is not None else 0}")
            print(df_k_data.tail(5) if df_k_data is not None else "K-line data is None")
            logger.info(msg="Cleaning K-line data")
            if df_k_data is not None:
                df_k_data_cleaned = clean_k_data(df_k_data)
                logger.info(msg="Calculating post-adjustment and future returns")
                df_k_data = cal_hfq_vectorized(df_k_data_cleaned, adjustment_cycles=adjustment_cycle)
        except Exception as e:
            error_msg = f"Failed to fetch K-line data: {str(e)}"
            logger.error(msg=error_msg)
            raise
        logger.info(
            msg=f"K-line data details - rows: {len(df_k_data) if df_k_data is not None else 0}, symbols: {len(df_k_data['symbol'].unique()) if df_k_data is not None else 0}")

        # Update status within the thread
        _db_handler.mongo_update(
            "panda",
            "tasks",
            {"task_id": task_id},
            {
                "process_status": 3,  # Started
                "updated_at": datetime.now().isoformat(),
            }
        )

        # Cleaning factor data
        logger.info(msg="2. Starting to clean factor data")
        try:

            factor_list = [df_factor.columns[2]]  # Get the name of the third column and convert to list
            logger.info(msg=f"Factor list: {factor_list}")
            df_factor = df_factor[~df_factor[factor_list[0]].isin([np.inf, -np.inf])]

            df_factor = df_factor.groupby('date', group_keys=False).apply(
                lambda x: ext_out_3std(x, factor_list[0]))  # 3-sigma extreme value processing
            logger.info(msg="Starting z_score processing")
            df_factor = df_factor.groupby('date', group_keys=False).apply(
                lambda x: z_score(x, factor_list))  # z-score standardization
        except Exception as e:
            error_msg = f"Failed to clean factor data: {str(e)}"
            logger.error(msg=error_msg, extra={"stage": "data_cleaning"})
            raise
        logger.info(
            msg=f"Factor data cleaning details stage: data_cleaning, rows: {len(df_factor) if df_factor is not None else 0}")

        # Update status within the thread
        _db_handler.mongo_update(
            "panda",
            "tasks",
            {"task_id": task_id},
            {
                "process_status": 4,  # Started
                "updated_at": datetime.now().isoformat(),
            }
        )

        # Merge data
        logger.info(msg="3. Starting to merge data")
        try:
            df = pd.merge(df_k_data, df_factor, on=['date', 'symbol'], how='left')
            df['date'] = pd.to_datetime(df['date'], format='%Y%m%d')
            df = df[df[factor_list].notna().all(axis=1)]
            df = df[df[f'{adjustment_cycle}day_return'].notna()]
        except Exception as e:
            error_msg = f"merge data failed: {str(e)}"
            logger.error(msg=error_msg)
            raise
        logger.info(msg=f"Data merge details, rows: {len(df) if df is not None else 0}")

        # Update status within the thread
        _db_handler.mongo_update(
            "panda",
            "tasks",
            {"task_id": task_id},
            {
                "process_status": 5,  # Started
                "updated_at": datetime.now().isoformat(),
            }
        )
        # Calculate lagged returns
        logger.info(msg="4. Starting to calculate lagged returns")
        try:
            df = cal_pct_lag(df)
        except Exception as e:
            error_msg = f"Failed to calculate lagged returns: {str(e)}"
            logger.error(msg=error_msg, extra={"stage": "return_calculation"})
            raise

        logger.info(msg="Lagged returns calculation completed")

        # Update status within the thread
        _db_handler.mongo_update(
            "panda",
            "tasks",
            {"task_id": task_id},
            {
                "process_status": 6,  # Started
                "updated_at": datetime.now().isoformat(),
            }
        )
        # Factor data grouping
        logger.info(msg=f"5. Starting factor data grouping, group number: {group_number}")
        try:
            # Use group number from parameters
            df_cuted, df_benchmark = grouping_factor(df=df, factor_name=factor_list[0],
                                                     adjustment_cycle=adjustment_cycle, group_cnt=group_number)
        except Exception as e:
            error_msg = f"Factor data grouping failed: {str(e)}"
            logger.error(msg=error_msg, extra={"stage": "grouping"})
            raise

        logger.info(
            msg=f"Factor grouping details, group number: {group_number}, benchmark date count: {len(df_benchmark) if df_benchmark is not None else 0}")

        # Update status within the thread
        _db_handler.mongo_update(
            "panda",
            "tasks",
            {"task_id": task_id},
            {
                "process_status": 7,  # Started
                "updated_at": datetime.now().isoformat(),
            }
        )

        def enrich_stock_data(df):
            # Get all unique stock codes
            symbols = df["symbol"].unique().tolist()

            # Query stock names from MongoDB
            query = {'symbol': {'$in': symbols}, 'expired': False}
            cursor = _db_handler.mongo_find(
                "panda",
                "stocks",  # Modify to the correct collection name
                query
            )

            # Create symbol to name mapping dictionary
            symbol_to_name = {item['symbol']: item['name'] for item in cursor}

            # Copy original DataFrame
            result_df = df.copy()

            # Add name column
            result_df['name'] = result_df["symbol"].map(symbol_to_name)

            return result_df

        last_date_top_factor_tmp = df_factor[df_factor['date'] == latest_date].sort_values(by=factor_list[0],
                                                                                           ascending=False).head(20)
        last_date_factor_tmp = df_factor[df_factor['date'] == latest_date].sort_values(by=factor_list[0],
                                                                                       ascending=False)
        last_date_top_factor_tmp = enrich_stock_data(last_date_top_factor_tmp)
        last_date_factor_tmp = enrich_stock_data(last_date_factor_tmp)
        # Progress bar: In-depth factor analysis

        logger.info(msg="6. Starting in-depth factor analysis")
        factor_obj_list = []
        for f in factor_list:
            try:
                logger.info(msg=f"Analyzing factor {f}")
                # Create factor object with group number
                factor_obj = factor(f, group_number=group_number, factor_id=factor_id)
                # Top 20 factor values for the latest date

                factor_obj.last_date_top_factor = last_date_top_factor_tmp
                factor_obj.logger = logger
                logger.info(msg=f"Retrieved Top20 factor values for latest date {latest_date}")

                factor_obj_list.append(
                    factor_obj)  # Create factor class object to store various backtest parameters and results
                # :param predict_direction: Prediction direction (0 for smaller factor value is better, IC is negative/1 for larger factor value is better, IC is positive)
                factor_obj.set_backtest_parameters(period=adjustment_cycle, predict_direction=factor_direction,
                                                   commission=0)

                logger.info(
                    msg=f"Set backtest parameters: period={adjustment_cycle}, predict_direction={factor_direction}, commission=0")
                logger.info(msg=f"Starting backtest for factor {f}")
                factor_obj.start_backtest(df_cuted, df_benchmark)
                logger.info(msg=f"Completed backtest for factor {f}")
                logger.info(msg=f"7. Saving analysis results for factor {f} to database...")
                # Update status within the thread
                _db_handler.mongo_update(
                    "panda",
                    "tasks",
                    {"task_id": task_id},
                    {
                        "process_status": 8,  # Started
                        "updated_at": datetime.now().isoformat(),
                    }
                )
                factor_obj.inset_to_database(factor_id, task_id)
                logger.info(msg=f"Analysis results for factor {f} saved")
            except Exception as e:
                error_msg = f"Factor {f} analysis failed: {str(e)}"
                logger.error(msg=error_msg, extra={"stage": "factor_analysis"})
                raise

        logger.info(msg="In-depth factor analysis completed", extra={"stage": "factor_analysis"})
        logger.info(msg="======= Factor analysis completed =======")

        # Update status within the thread
        _db_handler.mongo_update(
            "panda",
            "tasks",
            {"task_id": task_id},
            {
                "process_status": 9,  # Started
                "updated_at": datetime.now().isoformat(),
            }
        )

    except Exception as e:
        # Record overall error
        error_msg = f"factor analysis failed: {str(e)}"
        logger.error(msg=error_msg, extra={"stage": "error"})
        # Update task status to failed
        _db_handler.mongo_update(
            "panda",
            "tasks",
            {"task_id": task_id},
            {
                "process_status": -1,  # Failed
                "error_message": error_msg,
                "updated_at": datetime.now().isoformat(),
            }
        )
        raise  # Re-raise exception
    finally:
        return task_id


if __name__ == '__main__':
    import pandas as pd

    df = pd.read_csv("/Users/peiqi/code_new/python/panda_workflow/src/panda_server/11111.csv",
                     usecols=["date", "symbol", "factor1"],  # 只读取需要的列，节省内存
                     dtype={"date": str})  # 明确指定date列为字符串类型)
    factor_analysis_workflow(df_factor=df, adjustment_cycle=1, group_number=5, factor_direction=0)
