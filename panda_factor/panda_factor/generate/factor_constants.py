"""Constants used in factor generation and validation."""

class FactorConstants:
    # Factor name mapping
    FACTOR_MAP = {
        'price': 'close',
        'volume': 'volume',
        'open': 'open',
        'high': 'high',
        'low': 'low',
        'close': 'close',
        'amount': 'amount',
        'returns': 'returns',
        'turnover': 'turnover',
        'market_cap': 'market_cap',
    }

    # Add uppercase and mixed case versions
    FACTOR_MAP.update({k.upper(): v for k, v in FACTOR_MAP.items()})
    FACTOR_MAP.update({k.capitalize(): v for k, v in FACTOR_MAP.items()})

    # Allowed built-in functions and modules
    ALLOWED_BUILTINS = {
        # Basic math functions
        'abs', 'round', 'min', 'max', 'sum', 'len',
        'sin', 'cos', 'tan', 'log', 'exp', 'sqrt',
        
        # Basic calculation functions
        'RANK', 'RETURNS', 'STDDEV', 'CORRELATION', 'IF', 'MIN', 'MAX',
        'ABS', 'LOG', 'POWER', 'SIGN', 'SIGNEDPOWER', 'COVARIANCE',
        
        # Time series functions
        'DELAY', 'SUM', 'TS_ARGMAX', 'TS_ARGMIN', 'TS_MEAN', 'TS_MIN',
        'TS_MAX', 'TS_RANK', 'DECAY_LINEAR', 'MA', 'EMA', 'SMA', 'DMA', 'WMA',
        
        # Technical indicator functions
        'MACD', 'KDJ', 'RSI', 'BOLL', 'CCI', 'ATR', 'DMI', 'BBI', 'TAQ',
        'KTN', 'TRIX', 'VR', 'EMV', 'DPO', 'BRAR', 'MTM', 'MASS', 'ROC',
        'EXPMA', 'OBV', 'MFI', 'ASI', 'PSY', 'BIAS', 'WR',
        
        # Price-related functions
        'VWAP', 'CAP', 
        
        # Core utility functions
        'RD', 'RET', 'REF', 'DIFF', 'CONST', 'HHVBARS', 'LLVBARS', 'AVEDEV',
        'SLOPE', 'FORCAST', 'LAST', 'COUNT', 'EVERY', 'EXIST', 'FILTER',
        'SUMIF', 'BARSLAST', 'BARSLASTCOUNT', 'BARSSINCEN', 'CROSS',
        'LONGCROSS', 'VALUEWHEN',
        
        # Average functions
        'MEAN'
    }

    # Allowed module attributes
    ALLOWED_ATTRIBUTES = {
        'np': {
            # Basic math operations
            'mean', 'std', 'max', 'min', 'sum', 'abs', 'log', 'exp', 'sqrt',
            'where', 'nan', 'isnan', 'nanmean', 'nansum', 'nanstd',
            # Array operations
            'array', 'zeros', 'ones', 'full', 'arange', 'linspace',
            'concatenate', 'stack', 'vstack', 'hstack', 'reshape',
            # Statistical functions
            'median', 'percentile', 'quantile', 'var', 'cov', 'corrcoef',
            'average', 'cumsum', 'cumprod', 'diff', 'gradient',
            # Conditions and comparisons
            'all', 'any', 'greater', 'greater_equal', 'less', 'less_equal',
            'equal', 'not_equal', 'logical_and', 'logical_or', 'logical_not',
            # Math functions
            'sin', 'cos', 'tan', 'arcsin', 'arccos', 'arctan', 'sinh', 'cosh',
            'tanh', 'power', 'sign', 'floor', 'ceil', 'round', 'clip',
            # Others
            'inf', 'pi', 'e', 'newaxis'
        },
        'pd': {
            # Basic types
            'Series', 'DataFrame', 'Index', 'MultiIndex',
            # Data checking
            'isna', 'notna', 'isnull', 'notnull',
            # Data operations
            'concat', 'merge', 'to_datetime', 'date_range', 'DateOffset',
            'Timestamp', 'Timedelta', 'NaT',
            # Group operations
            'Grouper', 'TimeGrouper',
            # Others
            'NA', 'NaT', 'read_csv', 'read_excel', 'to_numeric'
        }
    }

    # Explicitly disallowed modules for security
    DISALLOWED_MODULES = {
        'os', 'subprocess', 'sys', 'builtins', 'eval', 'exec', 'globals',
        'locals', 'getattr', 'setattr', 'delattr', '__import__', 'open',
        'compile', 'file', 'execfile', 'shutil', 'pickle', 'shelve',
        'marshal', 'importlib', 'pty', 'platform', 'popen', 'commands'
    }

    # Allowed modules for import
    ALLOWED_IMPORTS = {
        'numpy', 'np',
        'pandas', 'pd',
        'math',
        'datetime', 'timedelta',
        'warnings',
        'Factor',  # Allow import from base class
        'talib',   # Technical analysis library
        'scipy',   # Scientific computing
        'sklearn', # Machine learning
        'statsmodels'  # Statistical models
    } 