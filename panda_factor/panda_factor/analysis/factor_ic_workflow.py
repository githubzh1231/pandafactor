import numpy as np
import pandas as pd
import warnings
import logging
import panda_data
from panda_factor.analysis.factor_func import *
from panda_factor.analysis.factor import factor
from tqdm.auto import tqdm  # Import tqdm for progress bars
from typing import Optional, Any
from panda_common.models.factor_analysis_params import Params
from panda_common.handlers.database_handler import DatabaseHandler
from panda_common.config import config
from panda_common.handlers.log_handler import get_factor_logger
import os
from datetime import datetime
import uuid
from loguru import logger


def factor_ic_workflow(df_factor: pd.DataFrame, adjustment_cycle, group_number, factor_direction) -> None:
    warnings.filterwarnings("ignore")

    # Get task ID from the task
    _db_handler = DatabaseHandler(config)
    start_time = sorted(df_factor["date"].unique())[0]
    end_time = sorted(df_factor["date"].unique())[-1]
    try:
        # Record analysis start
        logger.info("====== Starting factor ic ======")

        latest_date = df_factor['date'].max()
        logger.info(f"Latest date: {latest_date}")

        # Initialize data
        panda_data.init()

        # Get K-line data
        logger.info("1. Starting to fetch K-line data")
        try:
            df_k_data = panda_data.get_market_data(
                start_date=start_time,
                end_date=end_time
            )
            logger.info(f"k-line data length: {len(df_k_data) if df_k_data is not None else 0}")
            print(df_k_data.tail(5) if df_k_data is not None else "K-line data is None")
            logger.info("Cleaning K-line data")
            if df_k_data is not None:
                df_k_data_cleaned = clean_k_data(df_k_data)
                logger.info("Calculating post-adjustment and future returns")
                df_k_data = df_k_data_cleaned.groupby('symbol', group_keys=False).apply(cal_hfq)

        except Exception as e:
            error_msg = f"Failed to fetch K-line data: {str(e)}"
            logger.error(error_msg)
            raise
        logger.info(
            f"K-line data details - rows: {len(df_k_data) if df_k_data is not None else 0}, symbols: {len(df_k_data['symbol'].unique()) if df_k_data is not None else 0}")

        # Cleaning factor data
        logger.info("2. Starting to clean factor data")
        try:
            factor_list = df_factor.columns[2:]  # Get the name of the third column and convert to list
            logger.info(f"Factor list: {factor_list}")
            df_factor = df_factor.groupby('date', group_keys=False).apply(
                lambda x: ext_out_3std_list(x, factor_list))  # 3-sigma extreme value processing
            logger.info("Starting z_score processing")
            df_factor = df_factor.groupby('date', group_keys=False).apply(
                lambda x: z_score(x, factor_list))  # z-score standardization
        except Exception as e:
            error_msg = f"Failed to clean factor data: {str(e)}"
            logger.error(error_msg, extra={"stage": "data_cleaning"})
            raise
        logger.info(
            f"Factor data cleaning details stage: data_cleaning, rows: {len(df_factor) if df_factor is not None else 0}")

        # Merge data
        logger.info("3. Starting to merge data")
        try:
            df = pd.merge(df_k_data, df_factor, on=['date', 'symbol'], how='left')
            print(len(df))
            df['date'] = pd.to_datetime(df['date'], format='%Y%m%d')
            df = df[df[factor_list].notna().all(axis=1)]
            df = df[df[f'{adjustment_cycle}day_return'].notna()]
        except Exception as e:
            error_msg = f"merge data failed: {str(e)}"
            logger.error(error_msg)
            raise
        print(df.tail(5))
        logger.info(f"Data merge details, rows: {len(df) if df is not None else 0}")

        # Calculate lagged returns
        logger.info("4. Starting to calculate lagged returns")
        try:
            df = cal_pct_lag(df)
        except Exception as e:
            error_msg = f"Failed to calculate lagged returns: {str(e)}"
            logger.error(error_msg, extra={"stage": "return_calculation"})
            raise

        logger.info("Lagged returns calculation completed")

        # Factor data grouping
        logger.info(f"5. Starting factor data grouping, group number: {group_number}")
        try:
            # Use group number from parameters
            df_cuted, df_benchmark = grouping_factor_list(df, factor_list, group_number, logger)
        except Exception as e:
            error_msg = f"Factor data grouping failed: {str(e)}"
            logger.error(error_msg, extra={"stage": "grouping"})
            raise

        logger.info(
            f"Factor grouping details, group number: {group_number}, benchmark date count: {len(df_benchmark) if df_benchmark is not None else 0}")

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

        # last_date_top_factor_tmp = df_factor[df_factor['date'] == latest_date].sort_values(by=factor_list[0], ascending=False).head(20)
        # last_date_top_factor_tmp=enrich_stock_data(last_date_top_factor_tmp)
        # Progress bar: In-depth factor analysis
        logger.info("6. Starting in-depth factor analysis")
        factor_obj_list = []
        result_list = []
        for f in factor_list:
            try:
                logger.info(f"Analyzing factor {f}")
                # Create factor object with group number
                factor_obj = factor(f, group_number=group_number, factor_id="ic_analysis")
                # Top 20 factor values for the latest date

                # factor_obj.last_date_top_factor = last_date_top_factor_tmp
                factor_obj.logger = logger
                logger.info(f"Retrieved Top20 factor values for latest date {latest_date}")

                factor_obj_list.append(
                    factor_obj)  # Create factor class object to store various backtest parameters and results
                # :param predict_direction: Prediction direction (0 for smaller factor value is better, IC is negative/1 for larger factor value is better, IC is positive)
                factor_obj.set_backtest_parameters(period=adjustment_cycle, predict_direction=factor_direction,
                                                   commission=0)

                logger.info(
                    f"Set backtest parameters: period={adjustment_cycle}, predict_direction={factor_direction}, commission=0")
                logger.info(f"Starting backtest for factor {f}")
                factor_obj.start_backtest(df_cuted, df_benchmark)
                logger.info(f"Completed backtest for factor {f}")
                logger.info(f"7. Saving analysis results for factor {f} to database...")
                # Update status within the thread
                # factor_obj.inset_to_database(factor_id, task_id)
                # print(factor_obj.df_info2)
                result_list.append(factor_obj.df_info2.iloc[:, 0].loc["IC_mean"])
                logger.info(f"Analysis results for factor {f} saved")
            except Exception as e:
                error_msg = f"Factor {f} analysis failed: {str(e)}"
                logger.error(error_msg, extra={"stage": "factor_analysis"})
                raise

        logger.info("In-depth factor analysis completed", extra={"stage": "factor_analysis"})

        logger.info("======= Factor analysis completed =======")



    except Exception as e:
        # Record overall error
        error_msg = f"factor analysis failed: {str(e)}"
        logger.error(error_msg, extra={"stage": "error"})
        # Update task status to failed
        raise  # Re-raise exception
    finally:
        return r",".join(result_list)