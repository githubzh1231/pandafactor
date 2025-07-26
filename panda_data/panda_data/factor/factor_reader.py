import logging
from typing import Optional

import pandas as pd
import time
import traceback

from panda_common.handlers.database_handler import DatabaseHandler
from panda_common.logger_config import logger
from panda_data_hub.models.requestEntity import FactorsRequest


class FactorReader:
    def __init__(self, config):
        self.config = config
        # Initialize DatabaseHandler
        self.db_handler = DatabaseHandler(config)
        self.all_symbols = self.get_all_symbols()

    def _print_formula_error(self, e, formula, factor_logger: logging.Logger):
        """打印公式因子的错误信息"""
        if isinstance(e, SyntaxError):
            factor_logger.error("\n=== Formula Syntax Error ===")
            factor_logger.error(f"Error in formula: {formula}")
            factor_logger.error(f"Error message: {str(e)}")
            factor_logger.error(f"Error occurred at line {e.lineno}, offset {e.offset}")
            factor_logger.error(f"Text: {e.text}")
            return

        tb = traceback.extract_tb(e.__traceback__)
        if any('eval' in frame.name for frame in tb):
            # 公式执行错误
            factor_logger.error("\n=== Formula Execution Error ===")
            factor_logger.error(f"Error in formula: {formula}")
            factor_logger.error(f"Error message: {str(e)}")
            # 找到最后一个相关的错误帧
            last_frame = None
            for frame in reversed(tb):
                if 'eval' in frame.name:
                    last_frame = frame
                    break
            if last_frame:
                factor_logger.error(f"Error occurred at line {last_frame.lineno}")
                factor_logger.error(f"In expression: {last_frame.line}")
        else:
            # 公式设置错误
            factor_logger.error("\n=== Formula Setup Error ===")
            factor_logger.error(f"Error in formula setup: {str(e)}")
            factor_logger.error(f"Error type: {type(e)}")

    def _print_class_error(self, e, code, factor_logger):
        """打印类因子的错误信息"""
        tb = traceback.extract_tb(e.__traceback__)

        if isinstance(e, SyntaxError):
            factor_logger.error("\n=== Python Syntax Error ===")
            factor_logger.error(f"Error message: {str(e)}")
            factor_logger.error(f"Error occurred at line {e.lineno}, offset {e.offset}")
            factor_logger.error(f"Text: {e.text}")
            return

        # 检查是否是计算方法中的错误
        calc_frame = None
        for frame in tb:
            if 'calculate' in frame.name:
                calc_frame = frame
                break

        if calc_frame:
            # 因子计算错误
            factor_logger.error("\n=== Factor Calculation Error ===")
            factor_logger.error(f"Error in factor calculation:")
            factor_logger.error(f"Error message: {str(e)}")
            factor_logger.error(f"Error occurred at line {calc_frame.lineno} in calculate method")
            factor_logger.error(f"In code: {calc_frame.line}")
        else:
            # 因子类错误
            factor_logger.error("\n=== Factor Class Error ===")
            factor_logger.error(f"Error in factor class execution: {str(e)}")
            factor_logger.error(f"Error type: {type(e)}")

    def get_factor(self, symbols, factors, start_date, end_date, index_component: Optional[str] = None,
                   type: Optional[str] = 'stock'):
        all_data = []
        # Convert all factor names to lowercase
        if isinstance(factors, str):
            factors = factors.lower()
        elif isinstance(factors, list):
            factors = [f.lower() for f in factors]
        # 检查是否有基础因子
        base_factors = ["open", "close", "high", "low", "volume", "market_cap", "turnover", "amount"]
        requested_base_factors = [f for f in factors if f in base_factors]

        # 如果有基础因子，查一次库，再选择留什么字段
        if requested_base_factors:
            # 单次查询 factor_base 表
            query = {
                "date": {"$gte": start_date, "$lte": end_date}
            }
            if index_component:
                query['index_component'] = {"$eq": index_component}

            # 构建投影，只查询需要的字段
            base_fields = ['date', 'symbol']  # 基础字段
            projection = {field: 1 for field in base_fields + requested_base_factors}
            projection['_id'] = 0  # 不包含_id字段

            if type == 'future':
                # Add $expr condition to match symbol with underlying_symbol + "88"
                query["$expr"] = {
                    "$eq": [
                        "$symbol",
                        {"$concat": ["$underlying_symbol", "88"]}
                    ]
                }
                # 获取集合并使用批量优化
                collection = self.db_handler.get_mongo_collection(
                    self.config["MONGO_DB"],
                    "future_market"
                )
                cursor = collection.find(query, projection).batch_size(100000)
                records = list(cursor)
            else:
                # 获取集合并使用批量优化
                collection = self.db_handler.get_mongo_collection(
                    self.config["MONGO_DB"],
                    "factor_base"
                )
                cursor = collection.find(query, projection).batch_size(100000)
                records = list(cursor)

            if records:
                # Convert to DataFrame
                df = pd.DataFrame(records)
                all_data.append(df)

        if not all_data:
            logger.warning(f"No data found for the specified parameters")
            return None

        # Merge all dataframes on date and symbol
        result = all_data[0]
        for df in all_data[1:]:
            result = pd.merge(
                result,
                df,
                on=['date', 'symbol'],
                how='outer'
            )

        return result


    def get_custom_factor(self, factor_logger: logging.Logger, user_id, factor_name, start_date, end_date,
                          symbol_type: Optional[str] = 'stock'):
        try:
            # Check if factor table exists
            collection_name = f"factor_{factor_name}_{user_id}"
            if collection_name in self.db_handler.mongo_client[self.config["MONGO_DB"]].list_collection_names():
                # Query existing factor data
                query = {
                    "date": {
                        "$gte": start_date,
                        "$lte": end_date
                    }
                }

                # 使用hint强制使用索引
                records = self.db_handler.mongo_find(
                    self.config["MONGO_DB"],
                    collection_name,
                    query
                )

                if records:
                    df = pd.DataFrame(list(records))
                    df = df.set_index(['date', 'symbol'])
                    df = df.drop(columns=['_id'])
                    return df

                logger.warning(f"No data found in {collection_name} for the specified date range")
                return None

            start_time = time.time()
            query = {
                "user_id": str(user_id),
                "factor_name": factor_name,
            }
            # Get data from MongoDB
            records = self.db_handler.mongo_find(
                self.config["MONGO_DB"],
                "user_factors",
                query
            )
            logger.info(
                f"Query user_factors took {time.time() - start_time:.3f} seconds for {factor_name} start_date: {start_date} end_date: {end_date}")
            if len(records) == 0:
                logger.warning(f"No data found for the specified parameters")
                return None
            query = {}
            code_type = records[0]["code_type"]
            code = records[0]["code"]
            st = records[0]["params"].get('include_st', True)
            indicator = records[0]["params"].get('stock_pool', "000985")
            if indicator != "000985":
                if indicator == "000300":
                    query["index_component"] = "100"
                elif indicator == "000905":
                    query["index_component"] = "010"
                elif indicator == "000852":
                    query["index_component"] = "001"
            if not st:
                query["name"] = {"$not": {"$regex": "ST"}}
            collection = self.db_handler.get_mongo_collection(
                self.config["MONGO_DB"],
                "stock_market"
            )
            symbols = collection.distinct("symbol", query)

            if not symbols:
                logger.warning("No valid symbols found matching the criteria")
                return None

            # Lazy import MacroFactor to avoid circular dependency
            from panda_factor.generate.macro_factor import MacroFactor
            mf = MacroFactor()

            result = None
            try:
                if code_type == "formula":
                    result = mf.create_factor_from_formula(factor_logger, code, start_date, end_date, symbols,
                                                           symbol_type=symbol_type)
                elif code_type == "python":
                    result = mf.create_factor_from_class(factor_logger, code, start_date, end_date, symbols,
                                                         symbol_type=symbol_type)
                else:
                    logger.warning(f"Unknown code type: {code_type}")
                    return None

                if result is not None:
                    result = result.rename(columns={"value": factor_name})
                return result

            except Exception as e:
                if code_type == "formula":
                    self._print_formula_error(e, code, factor_logger)
                else:
                    self._print_class_error(e, code, factor_logger)
                return None

        except Exception as e:
            factor_logger.error("\n=== Factor Setup Error ===")
            factor_logger.error(f"Error in factor setup: {str(e)}")
            factor_logger.error(f"Error type: {type(e)}")
            return None

    def get_custom_factor_competition(self, factor_logger: logging.Logger, user_id, factor_id, start_date, end_date):
        try:

            start_time = time.time()
            query = {
                "userId": int(user_id),
                "factorId": factor_id,
            }
            # Get data from MongoDB
            records = self.db_handler.mongo_find(
                self.config["MONGO_DB"],
                "user_factor_submissions",
                query
            )
            logger.info(
                f"Query user_factors took {time.time() - start_time:.3f} seconds for {factor_id} start_date: {start_date} end_date: {end_date}")
            if len(records) == 0:
                logger.warning(f"No data found for the specified parameters")
                return None
            query = {}
            factor_name = records[0]["factorDetails"]["factor_name"]
            code_type = records[0]["factorDetails"]["code_type"]
            code = records[0]["factorDetails"]["code"]
            st = records[0]["factorDetails"]["params"]['include_st']
            indicator = records[0]["factorDetails"]["params"]['stock_pool']
            if indicator != "000985":
                if indicator == "000300":
                    query["index_component"] = "100"
                elif indicator == "000905":
                    query["index_component"] = "010"
                elif indicator == "000852":
                    query["index_component"] = "001"
            if not st:
                query["name"] = {"$not": {"$regex": "ST"}}
            collection = self.db_handler.get_mongo_collection(
                self.config["MONGO_DB"],
                "stock_market"
            )
            symbols = collection.distinct("symbol", query)

            if not symbols:
                logger.warning("No valid symbols found matching the criteria")
                return None

            # Lazy import MacroFactor to avoid circular dependency
            from panda_factor.generate.macro_factor import MacroFactor
            mf = MacroFactor()

            result = None
            try:
                if code_type == "formula":
                    result = mf.create_factor_from_formula(factor_logger, code, start_date, end_date, symbols)
                elif code_type == "python":
                    result = mf.create_factor_from_class(factor_logger, code, start_date, end_date, symbols)
                else:
                    logger.warning(f"Unknown code type: {code_type}")
                    return None

                if result is not None:
                    result = result.rename(columns={"value": factor_name})
                return result

            except Exception as e:
                if code_type == "formula":
                    self._print_formula_error(e, code, factor_logger)
                else:
                    self._print_class_error(e, code, factor_logger)
                return None

        except Exception as e:
            factor_logger.error("\n=== Factor Setup Error ===")
            factor_logger.error(f"Error in factor setup: {str(e)}")
            factor_logger.error(f"Error type: {type(e)}")
            return None

    def get_factor_by_name(self, factor_name, start_date, end_date):
        try:
            start_time = time.time()
            query = {
                "factor_name": factor_name,
            }
            # Get data from MongoDB
            records = self.db_handler.mongo_find(
                self.config["MONGO_DB"],
                "user_factors",
                query
            )
            logger.debug(
                f"Query user_factors took {time.time() - start_time:.3f} seconds for {factor_name} start_date: {start_date} end_date: {end_date}")
            if len(records) == 0:
                logger.warning(f"No data found for the specified parameters")
                return None
            query = {}
            code_type = records[0]["code_type"]
            code = records[0]["code"]

            # start_date = records[0]["params"]["start_date"]
            # end_date = records[0]["params"]["end_date"]
            st = records[0]["params"]['include_st']
            indicator = records[0]["params"]['stock_pool']
            if indicator != "000985":
                if indicator == "000300":
                    query["index_component"] = "100"
                elif indicator == "000905":
                    query["index_component"] = "010"
                elif indicator == "000852":
                    query["index_component"] = "001"
            if not st:
                query["name"] = {"$not": {"$regex": "ST"}}
            collection = self.db_handler.get_mongo_collection(
                self.config["MONGO_DB"],
                "stock_market"
            )
            symbols = collection.distinct("symbol", query)

            if not symbols:
                logger.warning("No valid symbols found matching the criteria")
                return None

            # Lazy import MacroFactor to avoid circular dependency
            from panda_factor.generate.macro_factor import MacroFactor
            mf = MacroFactor()

            result = None
            try:
                if code_type == "formula":
                    result = mf.create_factor_from_formula(logger, code, start_date, end_date, symbols)
                elif code_type == "python":
                    result = mf.create_factor_from_class(logger, code, start_date, end_date, symbols)
                else:
                    logger.warning(f"Unknown code type: {code_type}")
                    return None

                if result is not None:
                    result = result.rename(columns={"value": factor_name})
                return result

            except Exception as e:
                if code_type == "formula":
                    self._print_formula_error(e, code, logger)
                else:
                    self._print_class_error(e, code, logger)
                return None

        except Exception as e:
            logger.error("\n=== Factor Setup Error ===")
            logger.error(f"Error in factor setup: {str(e)}")
            logger.error(f"Error type: {type(e)}")
            return None

    def get_all_symbols(self):
        """Get all unique symbols using distinct command"""
        collection = self.db_handler.get_mongo_collection(
            self.config["MONGO_DB"],
            "stock_market"
        )
        return collection.distinct("symbol")