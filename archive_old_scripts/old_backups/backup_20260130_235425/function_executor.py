"""
Function Executor - Safely Execute AI-Selected Database Functions

Handles:
- Permission checking
- Function validation
- Safe execution with error handling
- Audit logging
- Response formatting

Usage:
    from function_executor import FunctionExecutor
    
    executor = FunctionExecutor()
    result = executor.execute("calculate_wcb_owed", {
        "start_date": "2024-01-01",
        "end_date": "2024-12-31"
    })
"""

import json
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime
from dataclasses import dataclass, asdict

# Import AI functions
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))
from ai_functions import AIFunctionRegistry


@dataclass
class ExecutionResult:
    """Result of function execution"""
    success: bool
    function_name: str
    result: Any = None
    error: str = None
    execution_time_ms: float = 0
    timestamp: str = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return asdict(self)
    
    def to_json(self) -> str:
        """Convert to JSON"""
        return json.dumps(self.to_dict(), default=str, indent=2)


class FunctionExecutor:
    """Execute AI-selected functions safely"""
    
    # Allowed functions (whitelist)
    ALLOWED_FUNCTIONS = {
        'get_trial_balance': {
            'permissions': ['read', 'analyst', 'admin'],
            'description': 'Get financial trial balance for a period'
        },
        'calculate_wcb_owed': {
            'permissions': ['read', 'analyst', 'admin'],
            'description': 'Calculate WCB liability'
        },
        'get_unpaid_charters': {
            'permissions': ['read', 'analyst', 'admin'],
            'description': 'Get list of unpaid charters'
        },
        'calculate_employee_pay': {
            'permissions': ['read', 'analyst', 'admin'],
            'description': 'Calculate employee payroll'
        },
        'get_monthly_summary': {
            'permissions': ['read', 'analyst', 'admin'],
            'description': 'Get monthly financial summary'
        },
        'check_missing_deductions': {
            'permissions': ['read', 'analyst', 'admin'],
            'description': 'Check for missing tax deductions'
        },
        'update_lms_data': {
            'permissions': ['write', 'admin'],  # Restricted!
            'description': 'Update LMS data (restricted)'
        },
    }
    
    def __init__(self, user_role: str = 'analyst', 
                 log_file: Optional[str] = None):
        """
        Initialize executor
        
        Args:
            user_role: User role (read, analyst, admin, write)
            log_file: Optional audit log file path
        """
        self.user_role = user_role
        self.registry = None  # Lazy initialization
        
        # Setup logging
        self.logger = logging.getLogger('FunctionExecutor')
        if not self.logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                '[%(levelname)s] %(asctime)s - %(message)s'
            )
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)
            self.logger.setLevel(logging.INFO)
        
        if log_file:
            file_handler = logging.FileHandler(log_file, mode='a')
            file_handler.setFormatter(formatter)
            self.logger.addHandler(file_handler)
    
    def _get_registry(self):
        """Lazy initialize registry"""
        if self.registry is None:
            self.registry = AIFunctionRegistry()
        return self.registry
    
    def check_permission(self, function_name: str) -> bool:
        """Check if user can execute function"""
        if function_name not in self.ALLOWED_FUNCTIONS:
            self.logger.warning(f"Function not found: {function_name}")
            return False
        
        required_perms = self.ALLOWED_FUNCTIONS[function_name]['permissions']
        
        if self.user_role not in required_perms:
            self.logger.warning(
                f"Permission denied: {self.user_role} -> {function_name}"
            )
            return False
        
        return True
    
    def validate_function(self, function_name: str) -> tuple[bool, str]:
        """Validate function exists and is allowed"""
        if function_name not in self.ALLOWED_FUNCTIONS:
            return False, f"Function '{function_name}' not found"
        
        # Try to get registry and check if function exists
        try:
            registry = self._get_registry()
            if not hasattr(registry, function_name):
                return False, f"Function '{function_name}' not in registry"
        except Exception as e:
            return False, f"Failed to initialize registry: {e}"
        
        return True, "OK"
    
    def execute(self, function_name: str, 
                args: Dict[str, Any] = None,
                user_id: Optional[str] = None) -> ExecutionResult:
        """
        Execute function safely
        
        Args:
            function_name: Function to execute
            args: Arguments as dictionary
            user_id: User ID for audit logging
        
        Returns:
            ExecutionResult with success/error status
        """
        start_time = datetime.now()
        
        # Validate function
        valid, msg = self.validate_function(function_name)
        if not valid:
            return ExecutionResult(
                success=False,
                function_name=function_name,
                error=msg,
                timestamp=datetime.now().isoformat()
            )
        
        # Check permissions
        if not self.check_permission(function_name):
            error_msg = f"Permission denied for user role '{self.user_role}'"
            self.logger.error(f"{function_name}: {error_msg}")
            return ExecutionResult(
                success=False,
                function_name=function_name,
                error=error_msg,
                timestamp=datetime.now().isoformat()
            )
        
        # Log execution attempt
        self.logger.info(
            f"Executing {function_name} with args {args} "
            f"(user_id={user_id}, role={self.user_role})"
        )
        
        try:
            # Get function from registry
            func = getattr(self._get_registry(), function_name)
            
            # Execute with args
            if args is None:
                args = {}
            
            result = func(**args)
            
            # Calculate execution time
            exec_time = (datetime.now() - start_time).total_seconds() * 1000
            
            self.logger.info(
                f"[SUCCESS] {function_name}: {type(result).__name__} "
                f"in {exec_time:.1f}ms"
            )
            
            return ExecutionResult(
                success=True,
                function_name=function_name,
                result=result,
                execution_time_ms=exec_time,
                timestamp=datetime.now().isoformat()
            )
        
        except TypeError as e:
            error_msg = f"Invalid arguments: {e}"
            self.logger.error(f"{function_name}: {error_msg}")
            return ExecutionResult(
                success=False,
                function_name=function_name,
                error=error_msg,
                timestamp=datetime.now().isoformat()
            )
        
        except Exception as e:
            error_msg = f"Execution failed: {str(e)}"
            self.logger.error(f"{function_name}: {error_msg}")
            return ExecutionResult(
                success=False,
                function_name=function_name,
                error=error_msg,
                timestamp=datetime.now().isoformat()
            )
    
    def list_available_functions(self) -> Dict[str, Dict[str, Any]]:
        """List available functions user can execute"""
        available = {}
        
        for func_name, info in self.ALLOWED_FUNCTIONS.items():
            # Check permission
            required_perms = info['permissions']
            if self.user_role not in required_perms:
                continue
            
            available[func_name] = {
                'description': info['description'],
                'permissions_required': required_perms,
                'allowed_for_user': True
            }
        
        return available
    
    def parse_function_call(self, llm_response: str) -> List[Dict[str, Any]]:
        """
        Parse function calls from LLM response
        
        Format expected: CALL_FUNCTION: function_name(arg1=val1, arg2=val2)
        
        Returns:
            List of {"function": str, "args": dict}
        """
        calls = []
        lines = llm_response.split('\n')
        
        for line in lines:
            if 'CALL_FUNCTION:' not in line:
                continue
            
            # Extract function call
            call_str = line.split('CALL_FUNCTION:')[1].strip()
            
            try:
                # Parse function_name(args)
                if '(' not in call_str or ')' not in call_str:
                    continue
                
                func_name = call_str[:call_str.index('(')].strip()
                args_str = call_str[call_str.index('(') + 1:call_str.rindex(')')].strip()
                
                # Parse arguments
                args = {}
                if args_str:
                    # Simple arg parsing (key=value, key=value)
                    for arg in args_str.split(','):
                        if '=' in arg:
                            key, val = arg.split('=', 1)
                            key = key.strip()
                            val = val.strip().strip('"\'')
                            args[key] = val
                
                calls.append({
                    'function': func_name,
                    'args': args
                })
            
            except Exception as e:
                print(f"Failed to parse function call: {call_str} - {e}")
        
        return calls
    
    def execute_function_call(self, call: Dict[str, Any], 
                            user_id: Optional[str] = None) -> ExecutionResult:
        """
        Execute a parsed function call
        
        Args:
            call: {"function": str, "args": dict}
            user_id: User ID for audit
        
        Returns:
            ExecutionResult
        """
        func_name = call.get('function', '')
        args = call.get('args', {})
        
        return self.execute(func_name, args, user_id)


def test_executor():
    """Test function executor"""
    print("=" * 80)
    print("FUNCTION EXECUTOR TEST")
    print("=" * 80)
    
    # Test 1: Create executor with analyst role
    print("\n[TEST 1] Executor Creation")
    print("-" * 80)
    executor = FunctionExecutor(user_role='analyst')
    print(f"Role: {executor.user_role}")
    print(f"Available functions: {len(executor.list_available_functions())}")
    
    # Test 2: List available functions
    print("\n[TEST 2] List Available Functions")
    print("-" * 80)
    available = executor.list_available_functions()
    for func_name, info in list(available.items())[:3]:
        print(f"  - {func_name}: {info['description']}")
    
    # Test 3: Execute read-only function
    print("\n[TEST 3] Execute Read-Only Function")
    print("-" * 80)
    result = executor.execute(
        'get_trial_balance',
        {'year': 2024, 'month': 12}
    )
    print(f"Success: {result.success}")
    print(f"Time: {result.execution_time_ms:.1f}ms")
    if result.error:
        print(f"Error: {result.error}")
    
    # Test 4: Permission denied test
    print("\n[TEST 4] Permission Denied Test")
    print("-" * 80)
    restricted_executor = FunctionExecutor(user_role='read')
    result = restricted_executor.execute('update_lms_data', {'reserve_number': '123'})
    print(f"Success: {result.success}")
    print(f"Error: {result.error}")
    
    # Test 5: Parse function calls from LLM
    print("\n[TEST 5] Parse Function Calls")
    print("-" * 80)
    llm_response = """
    Based on your question, I should call:
    CALL_FUNCTION: calculate_wcb_owed(start_date=2024-01-01, end_date=2024-12-31)
    
    This will give us the WCB liability.
    """
    
    calls = executor.parse_function_call(llm_response)
    print(f"Parsed calls: {len(calls)}")
    for call in calls:
        print(f"  - {call['function']}({call['args']})")
    
    # Test 6: Execute parsed call
    print("\n[TEST 6] Execute Parsed Call")
    print("-" * 80)
    if calls:
        result = executor.execute_function_call(calls[0])
        print(f"Success: {result.success}")
        print(f"Time: {result.execution_time_ms:.1f}ms")


if __name__ == "__main__":
    test_executor()
