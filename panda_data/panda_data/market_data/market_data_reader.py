from math import e
import pandas as pd
import time
from panda_common.handlers.database_handler import DatabaseHandler
from panda_common.logger_config import logger
import concurrent.futures
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any


class MarketDataReader:
    def __init__(self, config):
        self.config = config
        # Initialize DatabaseHandler
        self.db_handler = DatabaseHandler(config)
        self.all_symbols = self.get_all_symbols()

    def _chunk_date_range(self, start_date: str, end_date: str, chunk_months: int = 3) -> List[tuple]:
        """
        Split date range into smaller chunks for parallel processing.
        If start_date equals end_date, returns a single chunk with the same date.

        Args:
            start_date (str): Start date in YYYYMMDD format
            end_date (str): End date in YYYYMMDD format
            chunk_months (int): Number of months per chunk

        Returns:
            List[tuple]: List of (chunk_start, chunk_end) date tuples
        """
        start = datetime.strptime(start_date, "%Y%m%d")
        end = datetime.strptime(end_date, "%Y%m%d")

        # Handle single day case
        if start == end:
            return [(start_date, end_date)]

        chunks = []
        chunk_start = start

        while chunk_start <= end:  # Changed from < to <= to include end date
            # Calculate chunk_end
            chunk_end = min(
                chunk_start + timedelta(days=chunk_months * 30 - 1),  # Subtract 1 to not overlap with next chunk
                end
            )

            chunks.append((
                chunk_start.strftime("%Y%m%d"),
                chunk_end.strftime("%Y%m%d")
            ))

            # If we've reached or passed the end date, break
            if chunk_end >= end:
                break

            # Move to next chunk start
            chunk_start = chunk_end + timedelta(days=1)

        return chunks

    def _get_chunk_data(self, chunk_dates: tuple, query_params: Dict[str, Any], type: Optional[str] = 'stock') -> \
    Optional[pd.DataFrame]:
        """
        Get data for a specific date chunk
        """
        start_date, end_date = chunk_dates
        symbols = query_params['symbols']
        fields = query_params['fields']
        indicator = query_params['indicator']
        st = query_params['st']

        # Build query for this chunk
        # query = {
        #     "symbol": {"$in": symbols} if symbols else {"$exists": True},
        #     "date": {
        #         "$gte": start_date,
        #         "$lte": end_date
        #     }
        # }
        query = {}
        if start_date == end_date:
            # 如果是同一天，直接精确匹配
            query["date"] = start_date
        else:
            # 如果是不同日期，使用范围查询
            query["date"] = {
                "$gte": start_date,
                "$lte": end_date
            }

        if indicator != "000985":
            if indicator == "000300":
                query["index_component"] = "100"
            elif indicator == "000905":
                query["index_component"] = "010"
            elif indicator == "000852":
                query["index_component"] = "001"
        if not st:
            query["name"] = {"$not": {"$regex": "ST"}}
        # 构建投影
        projection = None
        if fields:
            projection = {field: 1 for field in fields + ['date', 'symbol']}
            if '_id' not in fields:
                projection['_id'] = 0

        # 估算每条记录的大小并设置合适的batch_size
        estimated_doc_size = len(fields) * 20 if fields else 200  # 假设每个字段平均20字节
        target_batch_size = min(
            max(
                int(10 * 1024 * 1024 / estimated_doc_size),  # 10MB / 每条记录大小
                2000  # 最小batch_size
            ),
            10000  # 最大batch_size
        )
        if type == 'future':
            query["$expr"] = {
                "$eq": [
                    "$symbol",
                    {"$concat": ["$underlying_symbol", "88"]}
                ]
            }
            collection = self.db_handler.get_mongo_collection(
                self.config["MONGO_DB"],
                "future_market"
            )
        else:
            collection = self.db_handler.get_mongo_collection(
                self.config["MONGO_DB"],
                "stock_market"
            )
        cursor = collection.find(
            query,
            projection=projection
        ).batch_size(target_batch_size)

        chunk_df = pd.DataFrame(list(cursor))
        if chunk_df.empty:
            return None

        if '_id' in chunk_df.columns:
            chunk_df = chunk_df.drop(columns=['_id'])

        return chunk_df

    def get_market_data(self, symbols=None, start_date=None, end_date=None, indicator="000985", st=True, fields=None,
                        type: Optional[str] = 'stock'):
        """
        Get market data for given symbols and date range using parallel processing

        Args:
            symbols: List of stock symbols or single symbol
            fields: List of fields to retrieve (e.g., ['open', 'close', 'volume'])
            start_date: Start date in YYYYMMDD format
            end_date: End date in YYYYMMDD format
            indicator: Index code for filtering
            st: Whether to include ST stocks

        Returns:
            pandas DataFrame with market data
        """
        start_time = time.time()

        # 参数验证
        if start_date is None or end_date is None:
            logger.error("start_date and end_date must be provided")
            return None

        # Convert parameters to list if they're not already
        if isinstance(symbols, str):
            symbols = [symbols]
        if isinstance(fields, str):
            fields = [fields]
        if fields is None:
            fields = []

        if symbols is None:
            symbols = self.all_symbols

        # 准备查询参数
        query_params = {
            'symbols': symbols,
            'fields': fields,
            'indicator': indicator,
            'st': st
        }

        # 将日期范围分成多个小块
        date_chunks = self._chunk_date_range(str(start_date), str(end_date))
        print(date_chunks)

        # 使用线程池并行处理每个块
        dfs = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
            futures = [
                executor.submit(self._get_chunk_data, chunk, query_params, str(type))
                for chunk in date_chunks
            ]

            for future in concurrent.futures.as_completed(futures):
                chunk_df = future.result()
                if chunk_df is not None and not chunk_df.empty:
                    dfs.append(chunk_df)

        if not dfs:
            logger.warning(f"No market data found for the specified parameters")
            return None

        # 合并所有数据块
        final_df = pd.concat(dfs, ignore_index=True)

        end_time = time.time()
        logger.info(f"Market data query and conversion took {end_time - start_time:.2f} seconds")

        return final_df

    def get_all_symbols(self):
        """Get all unique symbols using distinct command"""
        collection = self.db_handler.get_mongo_collection(
            self.config["MONGO_DB"],
            "stock_market"
        )
        return collection.distinct("symbol")