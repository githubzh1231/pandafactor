"""Error handling and logging utilities for factor generation."""

import ast
import traceback
from datetime import datetime
from typing import List, Dict, Any, Optional

class FactorErrorHandler:
    @staticmethod
    def format_error_stack(error: Exception, code: str) -> str:
        """Format error stack information, focusing on user code error location.
        
        Args:
            error: Exception caught
            code: User's original code
            
        Returns:
            Formatted error information
        """
        # Split user code into lines for easier display
        code_lines = [line.rstrip() for line in code.split('\n')]
        
        # Build error information
        error_msg = [f"Error type: {type(error).__name__}"]
        error_msg.append(f"Error message: {str(error)}")
        
        # Try to extract line number from error message
        line_no = None
        
        # Get full stack trace information
        tb_list = traceback.extract_tb(error.__traceback__)
        
        # Find user code error location
        for frame in reversed(tb_list):
            if frame.filename in ['<string>', '<unknown>']:
                code_line = frame.line if frame.line else ""
                if not code_line.strip():
                    continue
                    
                # Search for this line in code
                for i, line in enumerate(code_lines, 1):
                    if line.strip() and code_line.strip() in line.strip():
                        line_no = i
                        break
                if line_no:
                    break
        
        if line_no is None:
            # Try to extract from error message
            import re
            error_str = str(error)
            line_match = re.search(r'line (\d+)', error_str)
            if line_match:
                line_no = int(line_match.group(1))
                
            # Special handling for NameError
            if isinstance(error, NameError):
                var_match = re.search(r"name '(.+)' is not defined", str(error))
                if var_match:
                    var_name = var_match.group(1)
                    for i, line in enumerate(code_lines, 1):
                        if var_name in line:
                            line_no = i
                            break
        
        if line_no is not None:
            # Skip leading empty lines
            while line_no > 1 and not code_lines[line_no - 1].strip():
                line_no -= 1
                
            error_msg.append("\nCode location:")
            
            # Display code context
            start_line = max(0, line_no - 2)
            end_line = min(len(code_lines), line_no + 3)
            
            for i in range(start_line, end_line):
                if i < len(code_lines):
                    prefix = '>>> ' if i + 1 == line_no else '    '
                    error_msg.append(f"{prefix}{i + 1:2d} | {code_lines[i]}")
        else:
            error_msg.append("\nUnable to determine specific error line, displaying related code:")
            for i, line in enumerate(code_lines, 1):
                if line.strip():
                    error_msg.append(f"    {i:2d} | {line}")
        
        return '\n'.join(error_msg)

    @staticmethod
    def log_error_context(error: Exception, code: str, logger: Any) -> None:
        """Log detailed error context.
        
        Args:
            error: The exception that occurred
            code: The code being executed
            logger: Logger instance
        """
        def extract_factor_code(code: str) -> tuple[Optional[str], int]:
            """Extract the factor calculation code from the class definition."""
            import re
            
            match = re.search(r'def\s+calculate\s*\([^)]*\):\s*\n', code)
            if not match:
                return None, 0
                
            start_pos = match.end()
            lines = code[start_pos:].split('\n')
            
            # Skip empty lines
            i = 0
            while i < len(lines) and not lines[i].strip():
                i += 1
            if i >= len(lines):
                return None, 0
                
            first_line = lines[i]
            base_indent = len(first_line) - len(first_line.lstrip())
            
            # Extract method body
            method_lines = []
            method_start_line = code[:start_pos].count('\n') + i + 1
            
            for line in lines[i:]:
                if not line.strip() or len(line) - len(line.lstrip()) >= base_indent:
                    method_lines.append(line)
                else:
                    break
                    
            return '\n'.join(method_lines), method_start_line

        def find_error_location(tb, code: str) -> tuple[Optional[int], Optional[str], Optional[str]]:
            """Find the exact error location in the user's factor code."""
            while tb:
                frame = tb.tb_frame
                if 'calculate' in frame.f_code.co_name:
                    error_line = tb.tb_lineno - frame.f_code.co_firstlineno
                    factor_code, start_line = extract_factor_code(code)
                    if factor_code:
                        code_lines = factor_code.split('\n')
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
                line = code_lines[i].lstrip()
                if line.strip():
                    logger.error(f"{prefix}{i + 1:4d} | {line}")
        
        logger.error("=" * 50)
        
        # Add variable information for specific error types
        if isinstance(error, (AttributeError, TypeError)):
            logger.error(f"\n{type(error).__name__} Details:")
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
                        for key, value in locals_dict.items():
                            if isinstance(key, str) and not key.startswith('__'):
                                logger.error(f"Variable '{key}' is of type: {type(value)}")
                                if isinstance(value, (int, float, str, bool)):
                                    logger.error(f"Value: {value}")
            except Exception as e:
                logger.error(f"Could not determine variable details: {str(e)}")

    @staticmethod
    def create_custom_print(logger: Any):
        """Create a custom print function that includes timestamps and ignores file/flush params."""
        def custom_print(*args, **kwargs):
            # 过滤掉 print 的 file/flush 参数
            kwargs.pop('file', None)
            kwargs.pop('flush', None)
            msg = " ".join(str(arg) for arg in args)
            logger.info(f"{msg}")
        return custom_print 