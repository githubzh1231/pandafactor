# factors.py

import pandas as pd
import numpy as np
import re
import ast
from panda_factor.data.data_provider import PandaDataProvider
import time
from panda_common.logger_config import logger
from datetime import datetime
from panda_factor.generate.factor_utils import FactorUtils
from panda_factor.generate.factor_wrapper import FactorDataWrapper, FactorSeries
from panda_factor.generate.factor_constants import FactorConstants
from panda_factor.generate.factor_error_handler import FactorErrorHandler
from panda_factor.generate.factor_data_handler import FactorDataHandler
from typing import Optional, List, Set, Dict, Any


class MacroFactor:
    """Factor management class, responsible for factor creation and validation"""

    def _log_error_context(self, error, code, logger):
        """Helper function to log detailed error context"""
        import traceback
        import types
        import re

        def extract_factor_code(code):
            """Extract the factor calculation code from the class definition"""
            # Find the calculate method
            match = re.search(r'def\s+calculate\s*\([^)]*\):\s*\n', code)
            if not match:
                return None, 0

            start_pos = match.end()
            # Get the indentation of the first line after def calculate
            lines = code[start_pos:].split('\n')

            # Skip empty lines at the start
            i = 0
            while i < len(lines) and not lines[i].strip():
                i += 1
            if i >= len(lines):
                return None, 0

            first_line = lines[i]
            base_indent = len(first_line) - len(first_line.lstrip())

            # Extract the method body
            method_lines = []
            method_start_line = code[:start_pos].count('\n') + i + 1

            for line in lines[i:]:
                if not line.strip() or len(line) - len(line.lstrip()) >= base_indent:
                    method_lines.append(line)
                else:
                    break

            return '\n'.join(method_lines), method_start_line

        def find_error_location(tb, code):
            """Find the exact error location in the user's factor code"""
            while tb:
                frame = tb.tb_frame
                if 'calculate' in frame.f_code.co_name:
                    # Get the error line number in the frame
                    error_line = tb.tb_lineno - frame.f_code.co_firstlineno

                    # Extract the factor code
                    factor_code, start_line = extract_factor_code(code)
                    if factor_code:
                        # Get the code lines
                        code_lines = factor_code.split('\n')

                        # Find the last non-empty line before the error
                        actual_line = error_line
                        while actual_line > 0 and not code_lines[actual_line - 1].strip():
                            actual_line -= 1

                        return actual_line, factor_code, code_lines[actual_line - 1].lstrip()
                tb = tb.tb_next
            return None, None, None

        # Find error location
        error_line, factor_code, error_content = find_error_location(error.__traceback__, code)

        if error_line is None or factor_code is None:
            logger.error("Could not locate error in factor code")
            return

        # Split factor code into lines
        code_lines = factor_code.split('\n')

        # Log detailed error information
        logger.error("=" * 50)
        logger.error(f"Error Type: {type(error).__name__}")
        logger.error(f"Error Message: {str(error)}")
        logger.error(f"Error occurred in calculate method at line {error_line}")
        if error_content:
            logger.error(f"Last executed line: {error_content}")

        # Show code context
        logger.error("\nCode context:")
        context_start = max(0, error_line - 3)
        context_end = min(len(code_lines), error_line + 2)

        for i in range(context_start, context_end):
            if i < len(code_lines):
                prefix = ">>> " if i + 1 == error_line else "    "
                # Remove common indentation for better readability
                line = code_lines[i].lstrip()
                if line.strip():  # Only show non-empty lines
                    logger.error(f"{prefix}{i + 1:4d} | {line}")

        logger.error("=" * 50)

        # Add variable information
        if isinstance(error, AttributeError):
            logger.error("\nAttribute Error Details:")
            try:
                frame = None
                tb = error.__traceback__
                while tb:
                    if 'calculate' in tb.tb_frame.f_code.co_name:
                        frame = tb.tb_frame
                        break
                    tb = tb.tb_next

                if frame:
                    locals_dict = frame.f_locals
                    if isinstance(locals_dict, dict):
                        error_msg = str(error)
                        if "has no attribute" in error_msg:
                            attr_name = error_msg.split("'")[3]  # Extract attribute name
                            for key, value in locals_dict.items():
                                if key != '__traceback__':  # Skip traceback
                                    logger.error(f"Variable '{key}' is of type: {type(value)}")
                                    if isinstance(value, (int, float, str, bool)):
                                        logger.error(f"Value: {value}")
            except Exception as e:
                logger.error(f"Could not determine object details: {str(e)}")

        elif isinstance(error, TypeError):
            logger.error("\nType Error Details:")
            try:
                frame = None
                tb = error.__traceback__
                while tb:
                    if 'calculate' in tb.tb_frame.f_code.co_name:
                        frame = tb.tb_frame
                        break
                    tb = tb.tb_next

                if frame:
                    frame_locals = frame.f_locals
                    if isinstance(frame_locals, dict):
                        for key, value in frame_locals.items():
                            if isinstance(key, str) and not key.startswith('__'):
                                logger.error(f"Variable '{key}' is of type: {type(value)}")
                                if isinstance(value, (int, float, str, bool)):
                                    logger.error(f"Value: {value}")
            except Exception as e:
                logger.error(f"Could not determine variable types: {str(e)}")

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
        # Add uppercase version
        'PRICE': 'close',
        'VOLUME': 'volume',
        'OPEN': 'open',
        'HIGH': 'high',
        'LOW': 'low',
        'CLOSE': 'close',
        'AMOUNT': 'amount',
        'RETURNS': 'returns',
        'TURNOVER': 'turnover',
        'MARKET_CAP': 'market_cap',
        # Add mixed case version
        'Price': 'close',
        'Volume': 'volume',
        'Open': 'open',
        'High': 'high',
        'Low': 'low',
        'Close': 'close',
        'Amount': 'amount',
        'Returns': 'returns',
        'Turnover': 'turnover',
        'Market_Cap': 'market_cap',
    }

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

    # Get all public methods from FactorUtils
    ALLOWED_BUILTINS.update(
        {name for name in dir(FactorUtils) if not name.startswith('_')}
    )

    # Allowed module attributes
    ALLOWED_ATTRIBUTES = {
        'np': {
            # 基础数学运算
            'mean', 'std', 'max', 'min', 'sum', 'abs', 'log', 'exp', 'sqrt',
            'where', 'nan', 'isnan', 'nanmean', 'nansum', 'nanstd',
            # 数组操作
            'array', 'zeros', 'ones', 'full', 'arange', 'linspace',
            'concatenate', 'stack', 'vstack', 'hstack', 'reshape',
            # 统计函数
            'median', 'percentile', 'quantile', 'var', 'cov', 'corrcoef',
            'average', 'cumsum', 'cumprod', 'diff', 'gradient',
            # 条件和比较
            'all', 'any', 'greater', 'greater_equal', 'less', 'less_equal',
            'equal', 'not_equal', 'logical_and', 'logical_or', 'logical_not',
            # 数学函数
            'sin', 'cos', 'tan', 'arcsin', 'arccos', 'arctan', 'sinh', 'cosh',
            'tanh', 'power', 'sign', 'floor', 'ceil', 'round', 'clip',
            # 其他
            'inf', 'pi', 'e', 'newaxis'
        },
        'pd': {
            # 基础类型
            'Series', 'DataFrame', 'Index', 'MultiIndex',
            # 数据检查
            'isna', 'notna', 'isnull', 'notnull',
            # 数据操作
            'concat', 'merge', 'to_datetime', 'date_range', 'DateOffset',
            'Timestamp', 'Timedelta', 'NaT',
            # 分组操作
            'Grouper', 'TimeGrouper',
            # 其他
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
        'Factor',  # 允许从基类导入
        'talib',  # 技术分析库
        'scipy',  # 科学计算
        'sklearn',  # 机器学习
        'statsmodels'  # 统计模型
    }

    def __init__(self):
        """Initialize factor calculator"""
        self.data_provider = PandaDataProvider()
        self.data_handler = FactorDataHandler(self.data_provider)
        self.base_factors = None

    def _is_safe_name(self, name: str) -> bool:
        """Check if variable name is safe"""
        # If it's a factor name, allow directly
        if name in FactorConstants.FACTOR_MAP:
            return True

        # First check if it's an explicitly disallowed module
        if name in FactorConstants.DISALLOWED_MODULES:
            print(f"Module access denied: {name}")
            return False

        return (name in FactorConstants.ALLOWED_BUILTINS or
                name in FactorConstants.ALLOWED_ATTRIBUTES or
                name in FactorConstants.ALLOWED_IMPORTS or
                name in {'np', 'pd'} or
                not name.startswith('__'))

    def _is_safe_ast(self, node: ast.AST, allow_assign: bool = True,
                     error_info: Optional[List[Dict[str, Any]]] = None) -> bool:
        """Relaxed AST safety check: only block truly dangerous operations, allow all others."""
        if error_info is None:
            error_info = []

        # 危险模块和函数
        DANGEROUS_MODULES = {
            'os', 'subprocess', 'sys', 'shutil', 'pickle', 'shelve', 'marshal', 'importlib', 'pty', 'platform', 'popen',
            'commands'
        }
        DANGEROUS_FUNCS = {
            'eval', 'exec', 'open', 'compile', 'execfile', '__import__'
        }

        def add_error(node: ast.AST, reason: str) -> bool:
            try:
                line_no = getattr(node, 'lineno', 'unknown')
                col_offset = getattr(node, 'col_offset', 'unknown')
                code_str = ast.unparse(node) if hasattr(ast, 'unparse') else str(node)
                error_info.append({
                    'line': line_no,
                    'column': col_offset,
                    'type': type(node).__name__,
                    'code': code_str,
                    'reason': reason
                })
                print(f"Safety check failed at line {line_no}: {reason}")
                print(f"Code: {code_str}")
                return False
            except Exception:
                error_info.append({
                    'line': 'unknown',
                    'column': 'unknown',
                    'type': type(node).__name__,
                    'code': str(node),
                    'reason': reason
                })
                print(f"Safety check failed: {reason}")
                print(f"Node type: {type(node).__name__}")
                return False

        # 禁止危险模块导入
        if isinstance(node, ast.Import):
            for name in node.names:
                if name.name.split(".")[0] in DANGEROUS_MODULES:
                    return add_error(node, f"Import dangerous module: {name.name}")
            return True
        if isinstance(node, ast.ImportFrom):
            if node.module and node.module.split(".")[0] in DANGEROUS_MODULES:
                return add_error(node, f"Import from dangerous module: {node.module}")
            return True
        # 禁止危险模块属性访问
        if isinstance(node, ast.Attribute):
            if isinstance(node.value, ast.Name):
                if node.value.id in DANGEROUS_MODULES:
                    return add_error(node, f"Access dangerous module: {node.value.id}")
            return True
        # 禁止危险函数调用
        if isinstance(node, ast.Call):
            # 直接函数名
            if isinstance(node.func, ast.Name):
                if node.func.id in DANGEROUS_FUNCS:
                    return add_error(node, f"Call dangerous function: {node.func.id}")
            # 模块.函数
            if isinstance(node.func, ast.Attribute):
                if isinstance(node.func.value, ast.Name):
                    if node.func.value.id in DANGEROUS_MODULES:
                        return add_error(node, f"Call dangerous module function: {node.func.value.id}.{node.func.attr}")
            return True
        # 其他节点一律允许
        return True

    def _extract_factor_names(self, formula: str) -> Set[str]:
        """Extract required factor names from formula"""
        try:
            if not isinstance(formula, str):
                print(f"Formula must be string type, got {type(formula)}")
                return set()

            pattern = r'\b([a-zA-Z_][a-zA-Z0-9_]*)\b'
            variables = set(re.findall(pattern, formula))

            # Remove all built-in functions and attribute names
            variables = variables - FactorConstants.ALLOWED_BUILTINS - set(FactorConstants.ALLOWED_ATTRIBUTES.keys())

            factor_names = set()
            for var in variables:
                if var.upper() in FactorConstants.FACTOR_MAP:
                    factor_names.add(FactorConstants.FACTOR_MAP[var.upper()])
                elif var.lower() in FactorConstants.FACTOR_MAP:
                    factor_names.add(FactorConstants.FACTOR_MAP[var.lower()])
                elif var in FactorConstants.FACTOR_MAP:
                    factor_names.add(FactorConstants.FACTOR_MAP[var])

            if not factor_names:
                print(f"No valid factors found in formula. Variables found: {variables}")
            else:
                print(f"Required factors found: {factor_names}")

            return factor_names

        except Exception as e:
            print(f"Error extracting factor names: {e}")
            return set()

    def create_factor_from_formula(self, factor_logger: Any, formula: str, start_date: str,
                                   end_date: str, symbols: Optional[List[str]] = None,
                                   index_component: Optional[str] = None, symbol_type: Optional[str] = 'stock') -> \
    Optional[pd.DataFrame]:
        """Create factor from formula"""
        print("\n=== Starting formula execution ===")
        print(f"Formula: {formula}")

        # Validate formula
        if not isinstance(formula, str):
            raise ValueError("Formula must be string type")

        # Extract required factor names
        required_factors = self._extract_factor_names(formula)
        print(f"Required factors found: {required_factors}")

        # Get extended start date for lookback
        start_date_dt = pd.to_datetime(start_date)
        extended_start_date = (start_date_dt - pd.DateOffset(months=3)).strftime('%Y-%m-%d')

        # Create context
        context = {}

        # Get base factor data
        self.base_factors = self.data_handler.get_base_factors_pro(required_factors, extended_start_date, end_date,
                                                                   symbols, type=symbol_type)
        if self.base_factors is None or any(v is None for v in self.base_factors.values()):
            raise ValueError("Missing required base factors")

        # Add base factors to context
        for name, data in self.base_factors.items():
            context[name] = data
            context[name.upper()] = data
            print(f"Adding factor to context: {name} and {name.upper()}")

        # Add all FactorUtils methods to context
        for method_name in dir(FactorUtils):
            if not method_name.startswith('_'):
                method = getattr(FactorUtils, method_name)
                context[method_name] = method
                context[method_name.upper()] = method
                # print(f"Adding function to context: {method_name} and {method_name.upper()}")

        # Add math functions to context
        math_funcs = {
            'LOG': np.log, 'EXP': np.exp, 'SQRT': np.sqrt, 'ABS': np.abs,
            'SIN': np.sin, 'COS': np.cos, 'TAN': np.tan, 'POWER': np.power,
            'SIGN': np.sign, 'MAX': np.maximum, 'MIN': np.minimum,
            'MEAN': np.mean, 'STD': np.std
        }
        context.update(math_funcs)

        # Add numpy and pandas to context
        context['np'] = np
        context['pd'] = pd

        # Prepare result expression
        result_expr = formula.upper()
        print(f"Result expression: {result_expr}")

        # Execute formula
        print("Executing result expression")
        try:
            result = eval(result_expr, context)
            print(f"Result type: {type(result)}")
        except Exception as e:
            print(f"Formula execution error: {str(e)}")
            print("Functions available in context:")
            for key in sorted(context.keys()):
                if callable(context[key]):
                    print(f"- {key}")
            raise

        return self.data_handler.process_result(result, start_date)

    def create_factor_from_formula_pro(self, factor_logger: Any, formulas: List[str], start_date: str,
                                       end_date: str, symbols: Optional[List[str]] = None,
                                       index_component: Optional[str] = None, symbol_type: Optional[str] = 'stock') -> \
    Optional[pd.DataFrame]:
        """Create multiple factors from formulas in a single operation.

        Args:
            factor_logger: Logger instance
            formulas: List of formula strings to evaluate
            start_date: Start date for factor calculation
            end_date: End date for factor calculation
            symbols: Optional list of symbols to filter by

        Returns:
            DataFrame with columns named factor1, factor2, etc., or None if calculation fails
        """
        print("\n=== Starting multi-formula execution ===")
        print(f"Number of formulas: {len(formulas)}")

        # Validate input
        if not isinstance(formulas, list) or not all(isinstance(f, str) for f in formulas):
            raise ValueError("Formulas must be a list of strings")

        if not formulas:
            raise ValueError("Empty formulas list provided")

        # Extract required factor names from all formulas
        required_factors = set()
        for i, formula in enumerate(formulas):
            formula_factors = self._extract_factor_names(formula)
            required_factors.update(formula_factors)
            print(f"Formula {i + 1} requires factors: {formula_factors}")

        print(f"Total required factors: {required_factors}")

        # Get extended start date for lookback
        start_date_dt = pd.to_datetime(start_date)
        extended_start_date = (start_date_dt - pd.DateOffset(months=3)).strftime('%Y-%m-%d')

        # Create context
        context = {}

        # Get all base factor data at once
        self.base_factors = self.data_handler.get_base_factors_pro(required_factors, extended_start_date, end_date,
                                                                   symbols, type=symbol_type)
        if self.base_factors is None or any(v is None for v in self.base_factors.values()):
            raise ValueError("Missing required base factors")

        # Add base factors to context
        for name, data in self.base_factors.items():
            context[name] = data
            context[name.upper()] = data
            print(f"Adding factor to context: {name} and {name.upper()}")

        # Add all FactorUtils methods to context
        for method_name in dir(FactorUtils):
            if not method_name.startswith('_'):
                method = getattr(FactorUtils, method_name)
                context[method_name] = method
                context[method_name.upper()] = method
                # print(f"Adding function to context: {method_name} and {method_name.upper()}")

        # Add math functions to context
        math_funcs = {
            'LOG': np.log, 'EXP': np.exp, 'SQRT': np.sqrt, 'ABS': np.abs,
            'SIN': np.sin, 'COS': np.cos, 'TAN': np.tan, 'POWER': np.power,
            'SIGN': np.sign, 'MAX': np.maximum, 'MIN': np.minimum,
            'MEAN': np.mean, 'STD': np.std
        }
        context.update(math_funcs)

        # Add numpy and pandas to context
        context['np'] = np
        context['pd'] = pd

        # Execute each formula and collect results
        results = {}
        for i, formula in enumerate(formulas):
            factor_name = f"factor{i + 1}"
            print(f"Executing formula {i + 1}: {formula}")

            # Prepare result expression (convert to uppercase for consistency)
            result_expr = formula.upper()

            try:
                # Evaluate the formula
                result = eval(result_expr, context)
                # Store the result
                results[factor_name] = result

            except Exception as e:
                print(f"Formula {i + 1} execution error: {str(e)}")
                print("Functions available in context:")
                for key in sorted(context.keys()):
                    if callable(context[key]):
                        print(f"- {key}")
                raise ValueError(f"Error in formula {i + 1}: {str(e)}")

        # Create a combined DataFrame from all results
        try:
            # Create a DataFrame with all factors
            result_df = pd.DataFrame()

            # Process and add each factor
            for factor_name, result in results.items():
                # Process the result using the existing method
                processed_result = self.data_handler.process_result(result, start_date)

                if processed_result is not None:
                    # Rename the column to the factor name
                    processed_result.columns = [factor_name]

                    # If result_df is empty, initialize it
                    if result_df.empty:
                        result_df = processed_result
                    else:
                        # Join the result with the existing DataFrame
                        result_df = result_df.join(processed_result, how='outer')

            return result_df

        except Exception as e:
            print(f"Error combining results: {str(e)}")
            raise

    def create_factor_from_class(self, factor_logger: Any, class_code: str, start_date: str,
                                 end_date: str, symbols: Optional[List[str]] = None,
                                 index_component: Optional[str] = None, symbol_type: Optional[str] = 'stock') -> \
    Optional[pd.DataFrame]:
        """Create factor from class"""
        from .factor_loader import FactorLoader

        # Parse code and check safety
        try:
            tree = ast.parse(class_code)
            unsafe_operations = []
            error_details = []

            # Check all top-level nodes
            for node in tree.body:
                if not self._is_safe_ast(node, error_info=error_details):
                    unsafe_operations.append(f"Unsafe operation: {type(node).__name__}")

            if unsafe_operations:
                factor_logger.error("=== Code Safety Check Failed ===")
                factor_logger.error("Detailed error report:")
                for detail in error_details:
                    factor_logger.error(f"Line {detail['line']}, Column {detail['column']}:")
                    factor_logger.error(f"Code: {detail['code']}")
                    factor_logger.error(f"Reason: {detail['reason']}")
                    factor_logger.error("-" * 50)
                return None

            factor_logger.info("Code safety check passed")
        except SyntaxError as e:
            factor_logger.error(f"Code syntax error: {e}")
            factor_logger.error(f"Error location: Line {e.lineno}, Column {e.offset}")
            factor_logger.error(f"Error code: {e.text}")
            factor_logger.error(f"Error stack:\n{FactorErrorHandler.format_error_stack(e, class_code)}")
            return None
        except Exception as e:
            factor_logger.error(f"Code parsing error: {str(e)}")
            factor_logger.error(f"Error stack:\n{FactorErrorHandler.format_error_stack(e, class_code)}")
            return None

        try:
            # Load factor class
            factor_class = FactorLoader.load_factor_class(class_code, common_imports="""
import numpy as np
import pandas as pd
import math
from datetime import datetime, timedelta
import warnings
warnings.filterwarnings('ignore')
""")
            if factor_class is None:
                factor_logger.error("Factor class load failed")
                return None

            # Create factor instance
            factor = factor_class()
            factor.set_factor_logger(factor_logger)
            factor.print = FactorErrorHandler.create_custom_print(factor_logger)

        except Exception as e:
            factor_logger.error(f"Factor class initialization failed: {str(e)}")
            factor_logger.error(f"Error stack:\n{FactorErrorHandler.format_error_stack(e, class_code)}")
            return None

        try:
            # Extract required factors
            required_factors = set()

            # Find all dictionary subscript operations
            for node in ast.walk(tree):
                if (isinstance(node, ast.Subscript) and
                        isinstance(node.value, ast.Name) and
                        node.value.id == 'factors' and
                        isinstance(node.slice, ast.Constant)):
                    required_factors.add(node.slice.value)

            if not required_factors:
                factor_logger.error("No factor requirements found in code")
                return None
            # Convert required factors to lowercase
            required_factors = {factor.lower() for factor in required_factors}
            # Get extended start date
            start_date_dt = pd.to_datetime(start_date)
            extended_start_date = (start_date_dt - pd.DateOffset(months=3)).strftime('%Y-%m-%d')

            # Get required factors
            factors = self.data_handler.get_base_factors_pro(required_factors, extended_start_date, end_date, symbols,
                                                             index_component, type=symbol_type)
            if factors is None:
                return None

            # Use wrapper class to wrap factor data
            wrapped_factors = FactorDataWrapper(factors)

            # 自动全局替换print为logger.info
            import builtins
            old_print = builtins.print
            builtins.print = FactorErrorHandler.create_custom_print(factor_logger)
            try:
                # Calculate factor value
                result = factor.calculate(wrapped_factors)
            finally:
                builtins.print = old_print  # 恢复原print
            return self.data_handler.process_result(result, start_date)

        except Exception as e:
            factor_logger.error(f"Error occurred during factor processing: {str(e)}")
            factor_logger.error(f"Error stack:\n{FactorErrorHandler.format_error_stack(e, class_code)}")
            return None

    def validate_factor(self, code: str, code_type: str = 'formula', timeout: int = 5) -> Dict[str, Any]:
        """Validate factor code"""
        result = {
            'is_valid': True,
            'syntax_errors': [],
            'missing_factors': [],
            'formula_errors': [],
            'unsafe_operations': [],
            'timeout': False
        }

        try:
            # Parse code
            try:
                tree = ast.parse(code)
            except SyntaxError as e:
                result['is_valid'] = False
                result['syntax_errors'].append(f"Syntax error at line {e.lineno}: {e.msg}")
                return result

            # Check for unsafe operations
            error_info = []
            for node in ast.walk(tree):
                self._is_safe_ast(node, error_info=error_info)

            # Only collect important unsafe operations
            if error_info:
                result['is_valid'] = False
                for err in error_info:
                    result['unsafe_operations'].append(
                        f"Line {err['line']}: {err['type']} is not allowed - {err['reason']}"
                    )
                return result

        except Exception as e:
            result['is_valid'] = False
            result['syntax_errors'].append(f"Validation error: {str(e)}")

        return result