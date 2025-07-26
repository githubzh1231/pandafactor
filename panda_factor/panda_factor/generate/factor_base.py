from abc import ABC, abstractmethod

import numpy as np
import pandas as pd
from .factor_utils import FactorUtils


class Factor(ABC):
    """Base class for factors"""

    def __init__(self):
        self.logger = None
        # Copy all static methods from utility class to instance methods
        for method_name in dir(FactorUtils):
            if not method_name.startswith('_'):  # Skip private methods
                method = getattr(FactorUtils, method_name)
                setattr(self, method_name, method)

    def set_factor_logger(self, logger):
        self.logger = logger

    @abstractmethod
    def calculate(self, factors):
        """
        Calculate factor values
        Args:
            factors: Dictionary containing base factor data
        Returns:
            pd.Series: Calculated factor values
        """
        pass

    def RANK(self, series: pd.Series) -> pd.Series:
        """Cross-sectional ranking, normalized to [-0.5, 0.5] range"""

        def rank_group(group):
            valid_data = group.dropna()
            if len(valid_data) == 0:
                return pd.Series(0, index=group.index)
            ranks = valid_data.rank(method='average')
            ranks = (ranks - 1) / (len(valid_data) - 1) - 0.5
            result = pd.Series(index=group.index)
            result.loc[valid_data.index] = ranks
            result.fillna(0, inplace=True)
            return result

        result = series.groupby('date').apply(rank_group)
        if isinstance(result.index, pd.MultiIndex) and len(result.index.names) > 2:
            result = result.droplevel(0)
        return result

    def RETURNS(self, close: pd.Series) -> pd.Series:
        """Calculate returns"""

        def calculate_returns(group):
            group = group.sort_index(level='date')
            result = group.pct_change()
            result.iloc[0] = 0
            return result

        result = close.groupby(level='symbol', group_keys=False).apply(calculate_returns)
        return result

    def STDDEV(self, series: pd.Series, window: int = 20) -> pd.Series:
        """Calculate rolling standard deviation"""

        def rolling_std(group):
            group = group.sort_index(level='date')
            result = group.rolling(window=window, min_periods=max(2, window // 4)).std()
            return result

        result = series.groupby(level='symbol', group_keys=False).apply(rolling_std)
        return result

    def CORRELATION(self, series1: pd.Series, series2: pd.Series, window: int = 20) -> pd.Series:
        """Calculate rolling correlation coefficient"""
        result = pd.Series(index=series1.index, dtype=float)
        for symbol in series1.index.get_level_values('symbol').unique():
            s1 = series1[series1.index.get_level_values('symbol') == symbol]
            s2 = series2[series2.index.get_level_values('symbol') == symbol]
            s1, s2 = s1.align(s2)
            corr = s1.rolling(window=window).corr(s2)
            result[s1.index] = corr
        return result

    def IF(self, condition, true_value, false_value):
        """Conditional selection function"""
        return pd.Series(np.where(condition, true_value, false_value), index=condition.index)

    def DELAY(self, series: pd.Series, period: int = 1) -> pd.Series:
        """Calculate lagged values"""
        return series.groupby(level='symbol').shift(period)

    def SUM(self, series: pd.Series, window: int = 20) -> pd.Series:
        """Calculate rolling sum"""
        return series.groupby(level='symbol').rolling(window=window, min_periods=1).sum().droplevel(0)