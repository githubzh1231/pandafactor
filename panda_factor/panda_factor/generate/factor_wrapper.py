import pandas as pd
import numpy as np


class FactorSeries:
    def __init__(self, series):
        self.series = series

    def __getitem__(self, key):
        if isinstance(key, int) and key < 0:
            shifted = self.series.groupby(level='symbol').transform(lambda x: x.shift(-key))
            return shifted
        return self.series[key]

    def __getattr__(self, name):
        return getattr(self.series, name)

    def __add__(self, other):
        if isinstance(other, FactorSeries):
            return self.series + other.series
        return self.series + other

    def __sub__(self, other):
        if isinstance(other, FactorSeries):
            return self.series - other.series
        return self.series - other

    def __mul__(self, other):
        if isinstance(other, FactorSeries):
            return self.series * other.series
        return self.series * other

    def __truediv__(self, other):
        if isinstance(other, FactorSeries):
            return self.series / other.series
        return self.series / other

    def __pow__(self, other):
        if isinstance(other, FactorSeries):
            return self.series ** other.series
        return self.series ** other

    def __lt__(self, other):
        if isinstance(other, FactorSeries):
            return self.series < other.series
        return self.series < other

    def __gt__(self, other):
        if isinstance(other, FactorSeries):
            return self.series > other.series
        return self.series > other

    def __le__(self, other):
        if isinstance(other, FactorSeries):
            return self.series <= other.series
        return self.series <= other

    def __ge__(self, other):
        if isinstance(other, FactorSeries):
            return self.series >= other.series
        return self.series >= other

    def __eq__(self, other):
        if isinstance(other, FactorSeries):
            return self.series == other.series
        return self.series == other

    def __ne__(self, other):
        if isinstance(other, FactorSeries):
            return self.series != other.series
        return self.series != other


class FactorDataWrapper:
    def __init__(self, data_dict):
        self.data_dict = data_dict

    def __getitem__(self, key):

        if isinstance(key, str):
            key = key.lower()
            if key not in self.data_dict:
                print(f"Key {key} not found")
                raise KeyError(f"Factor {key} not found")
            series = self.data_dict[key]
            if not isinstance(series, pd.Series):
                series = pd.Series(series)
            return FactorSeries(series)

        print(f"Invalid key type: {type(key)}")
        raise KeyError(f"Invalid key type: {type(key)}")

    def __setitem__(self, key, value):
        print(f"\nSetting factor with key: {key}")
        self.data_dict[key] = value