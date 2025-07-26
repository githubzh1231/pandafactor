from panda_common.logger_config import logger
from panda_common.handlers.database_handler import DatabaseHandler
import pandas as pd
import time
import hashlib
import json
import os
from functools import lru_cache
import numpy as np
from concurrent.futures import ThreadPoolExecutor
import pickle
import datetime


class PartitionedMarketDataReader:
    """
    Market data reader that uses date-partitioned collections for improved performance
    """

    def __init__(self, config):
        self.config = config
        # Initialize DatabaseHandler
        self.db_handler = DatabaseHandler(config)
        # Get MongoDB database
        self.db = self.db_handler.mongo_client[config["MONGO_DB"]]
        # Cache for market data
        self._cache = {}
        # Cache expiration time (in seconds)
        self.cache_expiry = 3600  # 1 hour
        # Disk cache directory
        self.disk_cache_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'cache')
        os.makedirs(self.disk_cache_dir, exist_ok=True)
        # Thread pool for parallel processing
        self.executor = ThreadPoolExecutor(max_workers=4)
        # Available years with partitioned collections
        self._available_years = self._get_available_years()
        # All symbols (cached)
        self.all_symbols = self.get_all_symbols()

    def _get_available_years(self):
        """Get available years with partitioned collections"""
        available_years = []
        for collection_name in self.db.list_collection_names():
            if collection_name.startswith('stock_market_') and collection_name[13:].isdigit():
                year = int(collection_name[13:])
                available_years.append(year)

        # Also check if main collection exists
        if 'stock_market' in self.db.list_collection_names():
            available_years.append(0)  # 0 represents the main collection

        return sorted(available_years)

    def get_market_data(self, symbols, start_date, end_date, fields=None, batch_size=5000, use_disk_cache=True,
                        parallel=True):
        """
        Get market data for given symbols and date range using partitioned collections

        Args:
            symbols: List of stock symbols or single symbol
            fields: List of fields to retrieve (e.g., ['open', 'close', 'volume'])
            start_date: Start date in YYYYMMDD format
            end_date: End date in YYYYMMDD format
            batch_size: Number of records to fetch in each batch
            use_disk_cache: Whether to use disk cache
            parallel: Whether to use parallel processing for large queries

        Returns:
            pandas DataFrame with market data
        """
        start_time = time.time()

        # Generate cache key
        cache_key = self._generate_cache_key(symbols, start_date, end_date, fields)

        # Check memory cache first (fastest)
        if cache_key in self._cache:
            cache_entry = self._cache[cache_key]
            if time.time() - cache_entry['timestamp'] < self.cache_expiry:
                logger.debug(f"Using memory cached market data for {start_date} to {end_date}")
                return cache_entry['data']

        # Check disk cache if enabled
        if use_disk_cache:
            disk_cache_path = os.path.join(self.disk_cache_dir, f"{cache_key}.pkl")
            if os.path.exists(disk_cache_path):
                cache_timestamp = os.path.getmtime(disk_cache_path)
                if time.time() - cache_timestamp < self.cache_expiry:
                    try:
                        logger.debug(f"Using disk cached market data for {start_date} to {end_date}")
                        with open(disk_cache_path, 'rb') as f:
                            df = pickle.load(f)
                        # Also update memory cache
                        self._cache[cache_key] = {
                            'data': df,
                            'timestamp': time.time()
                        }
                        return df
                    except Exception as e:
                        logger.warning(f"Failed to load disk cache: {str(e)}")

        # If fields is None, return all fields
        if fields is None:
            fields = []

        # Convert parameters to list if they're not already
        if isinstance(symbols, str):
            symbols = [symbols]
        if isinstance(fields, str):
            fields = [fields]

        if symbols is None:
            symbols = self.all_symbols

        # Determine which years the query spans
        start_year = int(start_date[:4])
        end_year = int(end_date[:4])

        # Check if we can use partitioned collections
        if not self._available_years or (0 in self._available_years and len(self._available_years) == 1):
            # No partitioned collections available, use main collection
            logger.debug("No partitioned collections available, using main collection")
            return self._get_market_data_from_main(symbols, start_date, end_date, fields, batch_size, parallel)

        # Use parallel processing for multiple years if enabled
        if parallel and end_year > start_year:
            logger.debug(f"Using parallel processing for years {start_year} to {end_year}")
            return self._get_market_data_parallel(symbols, start_date, end_date, fields, batch_size)
        else:
            # Sequential processing
            all_data = []

            # Process each year
            for year in range(start_year, end_year + 1):
                year_data = self._get_market_data_for_year(symbols, start_date, end_date, year, fields, batch_size)
                if year_data is not None:
                    all_data.append(year_data)

            if not all_data:
                logger.warning(f"No market data found for the specified parameters")
                return None

            # Combine all data
            df = pd.concat(all_data, ignore_index=True)

            # Optimize DataFrame memory usage
            df = self._optimize_dataframe(df)

            # Cache the result in memory
            self._cache[cache_key] = {
                'data': df,
                'timestamp': time.time()
            }

            # Cache to disk if enabled
            if use_disk_cache:
                try:
                    with open(disk_cache_path, 'wb') as f:
                        pickle.dump(df, f, protocol=4)
                except Exception as e:
                    logger.warning(f"Failed to write disk cache: {str(e)}")

            # Manage cache size
            if len(self._cache) > 100:
                self._clear_old_cache()

            query_time = time.time() - start_time
            logger.info(f"Market data query completed in {query_time:.2f} seconds, {len(df)} records retrieved")

            return df

    def _get_market_data_parallel(self, symbols, start_date, end_date, fields, batch_size):
        """Get market data using parallel processing for multiple years"""
        start_year = int(start_date[:4])
        end_year = int(end_date[:4])

        # Define worker function
        def fetch_year(year):
            return self._get_market_data_for_year(symbols, start_date, end_date, year, fields, batch_size)

        # Execute in parallel
        years_to_process = list(range(start_year, end_year + 1))
        results = list(self.executor.map(fetch_year, years_to_process))

        # Combine results
        dfs = [df for df in results if df is not None]
        if not dfs:
            return None

        return pd.concat(dfs, ignore_index=True)

    def _get_market_data_for_year(self, symbols, start_date, end_date, year, fields, batch_size):
        """Get market data for a specific year"""
        # Determine collection name for this year
        collection_name = f"stock_market_{year}"

        # Check if collection exists
        if collection_name not in self.db.list_collection_names():
            # If year is in available years but collection doesn't exist, try main collection
            if 0 in self._available_years:
                logger.debug(f"Collection {collection_name} not found, trying main collection for year {year}")
                return self._get_market_data_from_main_for_year(symbols, start_date, end_date, year, fields, batch_size)
            else:
                logger.debug(
                    f"Collection {collection_name} not found and main collection not available, skipping year {year}")
                return None

        # Adjust date range for this year
        year_start = max(start_date, f"{year}0101")
        year_end = min(end_date, f"{year}1231")

        # Skip if year is outside the requested range
        if year_start > year_end:
            return None

        logger.debug(f"Querying {collection_name} for dates {year_start} to {year_end}")

        # Build query
        query = {
            "symbol": {"$in": symbols},
            "date": {
                "$gte": year_start,
                "$lte": year_end
            }
        }

        # Create projection to only fetch required fields
        projection = None
        if fields:
            projection = {'_id': 0, 'date': 1, 'symbol': 1}
            for field in fields:
                projection[field] = 1

        # Get collection
        collection = self.db[collection_name]

        # Use cursor
        cursor = collection.find(
            query,
            projection=projection
        ).hint([("symbol", 1), ("date", 1)])  # Hint to use index

        # Process data in batches
        all_data = []
        batch = []
        count = 0

        for record in cursor:
            batch.append(record)
            count += 1

            if count % batch_size == 0:
                all_data.extend(batch)
                batch = []

        # Add remaining records
        if batch:
            all_data.extend(batch)

        if not all_data:
            logger.debug(f"No data found in {collection_name} for the specified parameters")
            return None

        # Convert to DataFrame
        df = pd.DataFrame(all_data)

        logger.debug(f"Retrieved {len(df)} records from {collection_name}")
        return df

    def _get_market_data_from_main(self, symbols, start_date, end_date, fields, batch_size, parallel):
        """Get market data from the main collection"""
        # Build query
        query = {
            "symbol": {"$in": symbols},
            "date": {
                "$gte": start_date,
                "$lte": end_date
            }
        }

        # Create projection to only fetch required fields
        projection = None
        if fields:
            projection = {'_id': 0, 'date': 1, 'symbol': 1}
            for field in fields:
                projection[field] = 1

        # Get collection
        collection = self.db["stock_market"]

        # Use cursor
        cursor = collection.find(
            query,
            projection=projection
        ).hint([("symbol", 1), ("date", 1)])  # Hint to use index

        # Process data in batches
        all_data = []
        batch = []
        count = 0

        for record in cursor:
            batch.append(record)
            count += 1

            if count % batch_size == 0:
                all_data.extend(batch)
                batch = []
                logger.debug(f"Processed {count} records")

        # Add remaining records
        if batch:
            all_data.extend(batch)

        if not all_data:
            logger.warning(f"No market data found for the specified parameters")
            return None

        # Convert to DataFrame
        df = pd.DataFrame(all_data)

        # Optimize DataFrame memory usage
        return self._optimize_dataframe(df)

    def _get_market_data_from_main_for_year(self, symbols, start_date, end_date, year, fields, batch_size):
        """Get market data for a specific year from the main collection"""
        # Adjust date range for this year
        year_start = max(start_date, f"{year}0101")
        year_end = min(end_date, f"{year}1231")

        # Skip if year is outside the requested range
        if year_start > year_end:
            return None

        logger.debug(f"Querying main collection for year {year}, dates {year_start} to {year_end}")

        # Build query
        query = {
            "symbol": {"$in": symbols},
            "date": {
                "$gte": year_start,
                "$lte": year_end
            }
        }

        # Create projection to only fetch required fields
        projection = None
        if fields:
            projection = {'_id': 0, 'date': 1, 'symbol': 1}
            for field in fields:
                projection[field] = 1

        # Get collection
        collection = self.db["stock_market"]

        # Use cursor
        cursor = collection.find(
            query,
            projection=projection
        ).hint([("symbol", 1), ("date", 1)])  # Hint to use index

        # Process data
        all_data = list(cursor)

        if not all_data:
            logger.debug(f"No data found in main collection for year {year}")
            return None

        # Convert to DataFrame
        df = pd.DataFrame(all_data)

        logger.debug(f"Retrieved {len(df)} records from main collection for year {year}")
        return df

    def _optimize_dataframe(self, df):
        """Optimize DataFrame memory usage"""
        if df is None or len(df) == 0:
            return df

        # Convert date to datetime if it's not already
        if 'date' in df.columns and not pd.api.types.is_datetime64_any_dtype(df['date']):
            df['date'] = pd.to_datetime(df['date'], format='%Y%m%d')

        # Optimize numeric columns
        for col in df.select_dtypes(include=['float64']).columns:
            # Downcast float64 to float32
            df[col] = pd.to_numeric(df[col], downcast='float')

        # Optimize integer columns
        for col in df.select_dtypes(include=['int64']).columns:
            # Downcast int64 to smaller integer types
            df[col] = pd.to_numeric(df[col], downcast='integer')

        # Optimize object columns (usually strings)
        for col in df.select_dtypes(include=['object']).columns:
            if col == 'symbol':
                # Convert symbols to category for better memory usage
                df[col] = df[col].astype('category')

        return df

    def _generate_cache_key(self, symbols, start_date, end_date, fields):
        """Generate a unique cache key based on query parameters"""
        # Create a dictionary of parameters
        params = {
            'symbols': sorted(symbols) if isinstance(symbols, list) else symbols,
            'start_date': start_date,
            'end_date': end_date,
            'fields': sorted(fields) if isinstance(fields, list) and fields else 'all'
        }

        # Convert to JSON and hash
        params_str = json.dumps(params, sort_keys=True)
        return hashlib.md5(params_str.encode()).hexdigest()

    def _clear_old_cache(self):
        """Remove oldest entries from cache"""
        # Sort by timestamp and keep only the 50 most recent entries
        sorted_cache = sorted(
            self._cache.items(),
            key=lambda x: x[1]['timestamp'],
            reverse=True
        )[:50]
        self._cache = dict(sorted_cache)

        # Also clean up old disk cache files
        current_time = time.time()
        for filename in os.listdir(self.disk_cache_dir):
            if filename.endswith('.pkl'):
                file_path = os.path.join(self.disk_cache_dir, filename)
                if current_time - os.path.getmtime(file_path) > self.cache_expiry * 2:
                    try:
                        os.remove(file_path)
                    except Exception as e:
                        logger.warning(f"Failed to remove old cache file {filename}: {str(e)}")

    @lru_cache(maxsize=1)
    def get_all_symbols(self):
        """Get all unique symbols from all collections"""
        all_symbols = set()

        # Check main collection first
        if 'stock_market' in self.db.list_collection_names():
            main_symbols = self.db["stock_market"].distinct("symbol")
            all_symbols.update(main_symbols)

        # Check year collections
        for year in self._available_years:
            if year == 0:  # Skip main collection (already processed)
                continue

            collection_name = f"stock_market_{year}"
            if collection_name in self.db.list_collection_names():
                year_symbols = self.db[collection_name].distinct("symbol")
                all_symbols.update(year_symbols)

        return list(all_symbols)

    def get_available_fields(self):
        """Get all available fields from collections"""
        all_fields = set()

        # Check main collection first
        if 'stock_market' in self.db.list_collection_names():
            sample = self.db["stock_market"].find_one({})
            if sample:
                all_fields.update([field for field in sample.keys() if field != '_id'])

        # Check year collections
        for year in self._available_years:
            if year == 0:  # Skip main collection (already processed)
                continue

            collection_name = f"stock_market_{year}"
            if collection_name in self.db.list_collection_names():
                sample = self.db[collection_name].find_one({})
                if sample:
                    all_fields.update([field for field in sample.keys() if field != '_id'])

        return list(all_fields)

    def clear_cache(self):
        """Clear all caches"""
        self._cache = {}
        # Clear disk cache
        for filename in os.listdir(self.disk_cache_dir):
            if filename.endswith('.pkl'):
                try:
                    os.remove(os.path.join(self.disk_cache_dir, filename))
                except Exception as e:
                    logger.warning(f"Failed to remove cache file {filename}: {str(e)}")
        logger.info("All caches cleared")

    def refresh_available_years(self):
        """Refresh the list of available years with partitioned collections"""
        self._available_years = self._get_available_years()
        logger.info(f"Available years refreshed: {self._available_years}")
        return self._available_years