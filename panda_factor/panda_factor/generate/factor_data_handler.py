"""Factor data retrieval and processing utilities."""

import pandas as pd
from concurrent.futures import ThreadPoolExecutor, as_completed
import time
from typing import Dict, List, Optional, Set
from panda_common.logger_config import logger
from panda_factor.data.data_provider import PandaDataProvider


class FactorDataHandler:
    def __init__(self, data_provider: PandaDataProvider):
        """Initialize factor data handler.

        Args:
            data_provider: Data provider instance for fetching factor data
        """
        self.data_provider = data_provider

    def get_base_factors(
            self,
            required_factors: Set[str],
            start_date: str,
            end_date: str,
            symbols: Optional[List[str]] = None
    ) -> Optional[Dict[str, pd.Series]]:
        """Get base factor data.

        Args:
            required_factors: Set of factor names to fetch
            start_date: Start date for data retrieval
            end_date: End date for data retrieval
            symbols: Optional list of symbols to filter by

        Returns:
            Dictionary mapping factor names to their data Series, or None if any fetch fails
        """
        if not required_factors:
            return None

        factor_data = {}

        def fetch_factor(factor_name: str, start_date: str, end_date: str,
                         symbols: Optional[List[str]], data_provider: PandaDataProvider) -> tuple[
            Optional[pd.Series], str]:
            """Fetch a single factor's data.

            Args:
                factor_name: Name of the factor to fetch
                start_date: Start date for data retrieval
                end_date: End date for data retrieval
                symbols: Optional list of symbols to filter by
                data_provider: Data provider instance

            Returns:
                Tuple of (factor data Series, factor name) or (None, factor name) if fetch fails
            """
            try:
                logger.info(f"Starting to get factor {factor_name}...")
                start_time = time.time()

                data = data_provider.get_factor_data(factor_name, start_date, end_date, symbols)
                if data is None:
                    logger.error(f"Factor retrieval failed: {factor_name}")
                    return None, factor_name

                # Clean and process data
                data = data.loc[:, ~data.columns.duplicated()]  # Drop duplicate columns
                data = data.set_index(['date', 'symbol'])
                data = data[~data.index.duplicated(keep='first')]

                logger.info(f"Successfully retrieved factor {factor_name}, took {time.time() - start_time:.2f} seconds")
                return pd.Series(data[factor_name]), factor_name
            except Exception as e:
                logger.error(f"Error retrieving factor {factor_name}: {str(e)}")
                return None, factor_name

        logger.info(f"Starting parallel factor data retrieval, {len(required_factors)} factors in total")
        start_time = time.time()

        # Use ThreadPoolExecutor for parallel data fetching
        with ThreadPoolExecutor(max_workers=min(len(required_factors), 10)) as executor:
            future_to_factor = {
                executor.submit(
                    fetch_factor,
                    factor_name,
                    start_date,
                    end_date,
                    symbols,
                    self.data_provider
                ): factor_name for factor_name in required_factors
            }

            for future in as_completed(future_to_factor):
                factor_name = future_to_factor[future]
                try:
                    factor_data_result, _ = future.result()
                    if factor_data_result is None:
                        logger.error(f"Factor {factor_name} retrieval failed")
                        return None
                    factor_data[factor_name] = factor_data_result
                    logger.info(f"Factor {factor_name} loaded into memory")
                except Exception as e:
                    logger.error(f"Error processing factor {factor_name}: {str(e)}")
                    return None

        logger.info(f"All factor data retrieval completed, total time taken {time.time() - start_time:.2f} seconds")
        return factor_data

    def get_base_factors_pro(
            self,
            required_factors: Set[str],
            start_date: str,
            end_date: str,
            symbols: Optional[List[str]] = None,
            index_component: Optional[str] = None,
            type: Optional[str] = 'stock'
    ) -> Optional[Dict[str, pd.Series]]:
        """Get base factor data in a single request.

        Args:
            required_factors: Set of factor names to fetch
            start_date: Start date for data retrieval
            end_date: End date for data retrieval
            symbols: Optional list of symbols to filter by

        Returns:
            Dictionary mapping factor names to their data Series, or None if fetch fails
        """
        if not required_factors:
            return None
        # Convert all factor names to lowercase
        required_factors = {factor.lower() for factor in required_factors}
        logger.info(f"Starting factor data retrieval, {len(required_factors)} factors in total")
        start_time = time.time()

        try:
            # Convert set to list
            factors_list = list(required_factors)

            # Extend start_date by 30 days to ensure enough data for calculations
            start_date_dt = pd.to_datetime(start_date)
            extended_start_date = (start_date_dt - pd.Timedelta(days=30)).strftime('%Y%m%d')
            end_date_formatted = pd.to_datetime(end_date).strftime('%Y%m%d')

            # Call panda_data.get_factor with all factors at once to minimize database queries
            import panda_data
            df_all = panda_data.get_factor(
                factors=factors_list,  # Pass all factors at once
                start_date=extended_start_date,
                end_date=end_date_formatted,
                symbols=symbols,
                index_component=index_component,
                type=type
            )

            if df_all is None or df_all.empty:
                logger.error("Factor retrieval failed: no data returned")
                return None

            # Clean and prepare DataFrame
            df_all = df_all.loc[:, ~df_all.columns.duplicated()]  # Drop duplicate columns

            # Set index
            if 'date' in df_all.columns and 'symbol' in df_all.columns:
                df_all = df_all.set_index(['date', 'symbol'])
            else:
                logger.error("Required columns 'date' and 'symbol' not found in data")
                return None

            df_all = df_all[~df_all.index.duplicated(keep='first')]

            # Create factor_data dictionary
            factor_data = {}
            missing_factors = []

            for factor_name in required_factors:
                if factor_name in df_all.columns:
                    factor_data[factor_name] = pd.Series(df_all[factor_name])
                    logger.info(f"Factor {factor_name} loaded into memory")
                else:
                    logger.error(f"Factor {factor_name} not found in retrieved data")
                    missing_factors.append(factor_name)

            if missing_factors:
                logger.error(f"Missing factors: {missing_factors}")
                return None

            logger.info(f"All factor data retrieval completed, total time taken {time.time() - start_time:.2f} seconds")
            return factor_data

        except Exception as e:
            logger.error(f"Error retrieving factors: {str(e)}")
            return None

    @staticmethod
    def process_result(result: pd.Series, start_date: str) -> pd.DataFrame:
        """Process and validate factor calculation result.

        Args:
            result: Factor calculation result
            start_date: Start date to filter from

        Returns:
            Processed DataFrame with factor values
        """
        # Ensure result is pandas Series
        if not isinstance(result, pd.Series):
            result = pd.Series(result)

        # Ensure result has correct index
        if not isinstance(result.index, pd.MultiIndex):
            result = pd.Series(result, index=pd.MultiIndex.from_tuples(
                [(d, s) for d, s in zip(result.index, result.index)],
                names=['date', 'symbol']
            ))

        # Ensure index names are correct
        if result.index.names != ['date', 'symbol']:
            result.index.names = ['date', 'symbol']

        # Ensure index is unique
        result = result[~result.index.duplicated(keep='first')]

        # Filter dates
        result = result[result.index.get_level_values('date') >= start_date]

        return result.to_frame(name='value')