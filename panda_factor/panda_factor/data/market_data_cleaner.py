import pandas as pd
from panda_common.logger_config import logger


class MarketDataCleaner:
    """Class for cleaning market data"""

    def __init__(self, data_provider):
        """Initialize with data provider"""
        self.data_provider = data_provider

    def clean_daily_market_data(self, date: str, symbols: list = None):
        """
        Clean daily market data for given date and symbols

        Args:
            date: Date in YYYYMMDD format
            symbols: Optional list of symbols to clean
        """
        try:
            logger.info(f"Starting to clean market data for date: {date}")

            # Log input parameters
            logger.debug(f"Input parameters - date: {date}, symbols: {symbols}")

            # Get raw data
            logger.info("Fetching raw market data")
            raw_data = self.data_provider.get_market_data(date, symbols)

            if raw_data is None or len(raw_data) == 0:
                logger.warning(f"No market data found for date: {date}")
                return

            logger.debug(f"Retrieved {len(raw_data)} records")

            try:
                # Basic data validation
                logger.info("Performing data validation")
                self._validate_market_data(raw_data)

                # Clean data
                logger.info("Cleaning market data")
                cleaned_data = self._clean_market_data(raw_data)

                # Save cleaned data
                logger.info("Saving cleaned data")
                self._save_market_data(cleaned_data, date)

                logger.info(f"Successfully cleaned market data for date: {date}")

            except ValueError as e:
                logger.error(f"Data validation failed: {str(e)}")
                return
            except Exception as e:
                logger.error(f"Error cleaning market data: {str(e)}")
                return

        except Exception as e:
            logger.error(f"Failed to clean market data for date {date}", exc_info=True)
            return

    def _validate_market_data(self, data: pd.DataFrame):
        """Validate market data"""
        logger.debug("Starting data validation")

        # Check required columns
        required_columns = {'date', 'symbol', 'open', 'high', 'low', 'close', 'volume'}
        missing_columns = required_columns - set(data.columns)

        if missing_columns:
            error_msg = f"Missing required columns: {missing_columns}"
            logger.error(error_msg)
            raise ValueError(error_msg)

        # Check for null values
        null_counts = data[list(required_columns)].isnull().sum()
        if null_counts.any():
            logger.warning(f"Found null values:\n{null_counts[null_counts > 0]}")

        # Check data types
        logger.debug("Checking data types")
        try:
            data['date'] = pd.to_datetime(data['date'])
            numeric_columns = ['open', 'high', 'low', 'close', 'volume']
            data[numeric_columns] = data[numeric_columns].astype(float)
        except Exception as e:
            error_msg = f"Data type conversion failed: {str(e)}"
            logger.error(error_msg)
            raise ValueError(error_msg)

        logger.debug("Data validation completed")

    def _clean_market_data(self, data: pd.DataFrame) -> pd.DataFrame:
        """Clean market data"""
        logger.debug("Starting data cleaning")

        # Make a copy to avoid modifying original data
        cleaned = data.copy()

        # Remove duplicates
        initial_len = len(cleaned)
        cleaned = cleaned.drop_duplicates()
        if len(cleaned) < initial_len:
            logger.warning(f"Removed {initial_len - len(cleaned)} duplicate records")

        # Handle missing values
        cleaned = cleaned.fillna(method='ffill')

        # Remove invalid prices
        price_mask = (cleaned[['open', 'high', 'low', 'close']] <= 0).any(axis=1)
        if price_mask.any():
            logger.warning(f"Removing {price_mask.sum()} records with invalid prices")
            cleaned = cleaned[~price_mask]

        # Remove invalid volume
        volume_mask = cleaned['volume'] < 0
        if volume_mask.any():
            logger.warning(f"Removing {volume_mask.sum()} records with invalid volume")
            cleaned = cleaned[~volume_mask]

        logger.debug(f"Data cleaning completed. Records: {len(cleaned)}")
        return cleaned

    def _save_market_data(self, data: pd.DataFrame, date: str):
        """Save cleaned market data"""
        try:
            logger.debug(f"Saving {len(data)} records for date {date}")
            self.data_provider.save_market_data(data, date)
            logger.debug("Data saved successfully")
        except Exception as e:
            logger.error(f"Failed to save market data: {str(e)}", exc_info=True)
            raise