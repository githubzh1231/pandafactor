import ast
import types
from typing import Type
from .factor_base import Factor
from datetime import datetime
import importlib.util
import sys
from .factor_utils import FactorUtils

class FactorLoader:
    """Load and validate custom factor classes"""
    
    @staticmethod
    def _is_safe_ast(node) -> bool:
        """Check if AST node is safe for factor calculation"""
        # Allow imports
        if isinstance(node, ast.Import):
            allowed_modules = {'numpy', 'pandas', 'talib', 'scipy', 'sklearn', 'math', 'datetime', 'warnings'}
            return all(name.name in allowed_modules for name in node.names)
            
        if isinstance(node, ast.ImportFrom):
            allowed_imports = {
                ('panda_factor.generate.factor_base', 'Factor'),
                ('scipy', 'stats'),
                ('sklearn', 'preprocessing'),
                ('datetime', 'datetime'),
                ('datetime', 'timedelta')
            }
            return (node.module, node.names[0].name) in allowed_imports
            
        # Allow class definition
        if isinstance(node, ast.ClassDef):
            # Check class name and base class
            if not node.name.isidentifier():
                print(f"Invalid class name: {node.name}")
                return False
            if len(node.bases) != 1 or not isinstance(node.bases[0], ast.Name) or node.bases[0].id != 'Factor':
                print("Custom factor class must inherit from Factor")
                return False
            # Check class body
            return all(FactorLoader._is_safe_ast(n) for n in node.body)
            
        # Allow function definition
        if isinstance(node, ast.FunctionDef):
            if node.name != 'calculate':
                print(f"Only calculate method is allowed, found: {node.name}")
                return False
            return all(FactorLoader._is_safe_ast(n) for n in node.body)
            
        # Allow basic literals
        if isinstance(node, (ast.Num, ast.Str, ast.Bytes, ast.NameConstant, ast.Constant)):
            return True
            
        # Allow names
        if isinstance(node, ast.Name):
            return True
            
        # Allow attribute access (for factor dictionary access)
        if isinstance(node, ast.Attribute):
            return True
            
        # Allow subscript (for dictionary access)
        if isinstance(node, ast.Subscript):
            return True
            
        # Allow basic mathematical operations
        if isinstance(node, (ast.BinOp, ast.UnaryOp)):
            return True
            
        # Allow basic expressions
        if isinstance(node, (ast.Expr, ast.Return)):
            return True
            
        # Allow arguments
        if isinstance(node, ast.arguments):
            return True
            
        # Allow function arguments
        if isinstance(node, ast.arg):
            return True
            
        # Allow assignments for intermediate calculations
        if isinstance(node, ast.Assign):
            return True
            
        # Allow function calls
        if isinstance(node, ast.Call):
            return True
            
        # Allow list and tuple literals
        if isinstance(node, (ast.List, ast.Tuple)):
            return True
            
        # Allow comparisons
        if isinstance(node, ast.Compare):
            return True
            
        # Allow if statements
        if isinstance(node, ast.If):
            return True
            
        # Allow for loops
        if isinstance(node, ast.For):
            return True
            
        # Allow while loops with break condition
        if isinstance(node, ast.While):
            return True
            
        # Allow break and continue
        if isinstance(node, (ast.Break, ast.Continue)):
            return True
            
        # Allow try-except blocks
        if isinstance(node, (ast.Try, ast.ExceptHandler)):
            return True
            
        # Disallow any other type of node
        print(f"Unsafe operation detected: {type(node).__name__}")
        return False
    
    @staticmethod
    def load_factor_class(class_code: str, common_imports: str = None) -> type:
        """
        加载因子类代码
        
        Args:
            class_code: 因子类代码字符串
            common_imports: 公共导入语句
            
        Returns:
            加载的因子类
        """
        try:
            # 创建一个新的模块
            spec = importlib.util.spec_from_loader('dynamic_factor', loader=None)
            module = importlib.util.module_from_spec(spec)
            
            # 准备代码
            setup_code = """
from panda_factor.generate.factor_base import Factor
from panda_factor.generate.factor_utils import FactorUtils
import pandas as pd
import numpy as np

# 从FactorUtils导入所有公共方法到全局命名空间
"""
            if common_imports:
                setup_code += common_imports
                
            # 添加FactorUtils的所有公共方法到全局命名空间
            method_code = ""
            for method_name in dir(FactorUtils):
                if not method_name.startswith('_'):  # 跳过私有方法
                    method_code += f"{method_name} = FactorUtils.{method_name}\n"
            
            setup_code += method_code
            
            # 组合完整代码
            full_code = setup_code + "\n" + class_code
            
            # 执行代码
            exec(full_code, module.__dict__)
            
            # 查找继承自Factor的类
            factor_class = None
            for item in module.__dict__.values():
                if isinstance(item, type) and issubclass(item, Factor) and item != Factor:
                    factor_class = item
                    break
            
            if factor_class is None:
                print("未找到有效的因子类")
                return None
                
            return factor_class
            
        except Exception as e:
            print(f"加载因子类时出错: {str(e)}")
            import traceback
            print(f"错误详情: {traceback.format_exc()}")
            return None 