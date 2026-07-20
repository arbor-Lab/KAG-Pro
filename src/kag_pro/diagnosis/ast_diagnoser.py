"""AST-assisted code diagnosis for university-level programming questions.

Parses student code submissions and detects common errors:
- Syntax errors
- Off-by-one errors in loops
- Missing base cases in recursion
- Complexity issues (suspected O(n²) where O(n) expected)
- Edge case handling (empty input, null checks)
"""

import ast
import re
from typing import List, Tuple


class ASTDiagnoser:
    """Analyze student code using AST parsing for common error patterns."""

    ERROR_CHECKS = [
        "syntax_error",
        "missing_base_case",
        "off_by_one",
        "infinite_loop_risk",
        "missing_return",
        "inefficient_algorithm",
        "no_input_validation",
    ]

    def diagnose(self, code: str, expected_complexity: str | None = None) -> dict:
        """Analyze code and return detected issues.

        Args:
            code: student's Python code
            expected_complexity: e.g., "O(n log n)" for comparison

        Returns:
            dict with errors list, suggestions, and severity
        """
        errors = []
        suggestions = []

        # 1. Syntax check
        syntax_ok, syntax_msg = self._check_syntax(code)
        if not syntax_ok:
            errors.append({"type": "syntax_error", "message": syntax_msg, "severity": "critical"})
            return {"errors": errors, "suggestions": ["Fix syntax errors before further analysis."], "severity": "critical"}

        try:
            tree = ast.parse(code)
        except SyntaxError as e:
            errors.append({"type": "syntax_error", "message": str(e), "severity": "critical"})
            return {"errors": errors, "suggestions": ["Fix syntax errors first."], "severity": "critical"}

        # 2. Missing base case in recursion
        funcs = [node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)]
        for func in funcs:
            if self._is_recursive(func, tree):
                has_base, base_msg = self._check_base_case(func)
                if not has_base:
                    errors.append({
                        "type": "missing_base_case",
                        "message": f"递归函数 '{func.name}' 缺少明确的终止条件",
                        "severity": "high",
                    })
                    suggestions.append(f"在 '{func.name}' 开头添加 if 判断作为递归终止条件。")

        # 3. Off-by-one in range()
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "range":
                off_by_one, ob_msg = self._check_off_by_one(node)
                if off_by_one:
                    errors.append({"type": "off_by_one", "message": ob_msg, "severity": "medium"})
                    suggestions.append("检查循环边界：是否该用 range(n+1) 或 range(1, n+1)？")

        # 4. Missing return
        for func in funcs:
            returns = [n for n in ast.walk(func) if isinstance(n, ast.Return)]
            has_return_outside_if = any(
                isinstance(r, ast.Return) and not self._is_inside_if(r, func)
                for r in ast.walk(func) if isinstance(r, ast.Return)
            )
            if not returns:
                errors.append({
                    "type": "missing_return",
                    "message": f"函数 '{func.name}' 没有任何 return 语句",
                    "severity": "medium",
                })

        # 5. Complexity hint: nested loops = likely O(n²)
        loop_depths = self._max_loop_depth(tree)
        if loop_depths >= 2:
            errors.append({
                "type": "inefficient_algorithm",
                "message": f"检测到 {loop_depths} 层嵌套循环，可能是 O(n^{loop_depths}) 复杂度",
                "severity": "medium",
            })
            if expected_complexity and "log" in expected_complexity.lower():
                suggestions.append("考虑使用二分搜索或分治法降低复杂度。")

        # 6. No input validation / edge case handling
        if self._has_list_operations(tree) and not self._has_empty_check(tree):
            errors.append({
                "type": "no_input_validation",
                "message": "代码未检查输入是否为空（空列表/None）",
                "severity": "low",
            })
            suggestions.append("添加输入验证：if not data: return ...")

        severity = "critical" if any(e["severity"] == "critical" for e in errors) else                    "high" if any(e["severity"] == "high" for e in errors) else                    "medium" if errors else "low"

        return {
            "errors": errors,
            "suggestions": suggestions,
            "severity": severity,
            "error_count": len(errors),
        }

    # ---- Internal checkers ----

    def _check_syntax(self, code: str) -> Tuple[bool, str]:
        try:
            ast.parse(code)
            return True, ""
        except SyntaxError as e:
            return False, f"第{e.lineno}行: {e.msg}"

    def _is_recursive(self, func: ast.FunctionDef, tree: ast.AST) -> bool:
        for node in ast.walk(func):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                if node.func.id == func.name:
                    return True
        return False

    def _check_base_case(self, func: ast.FunctionDef) -> Tuple[bool, str]:
        for node in ast.walk(func):
            if isinstance(node, ast.If):
                # Check if the if block contains a return
                for child in ast.walk(node):
                    if isinstance(child, ast.Return):
                        return True, ""
        return False, "未找到明确的递归终止条件 (if ... return)"

    def _check_off_by_one(self, range_node: ast.Call) -> Tuple[bool, str]:
        args = range_node.args
        if len(args) == 1:
            arg = args[0]
            if isinstance(arg, ast.BinOp) and isinstance(arg.op, ast.Sub):
                return True, "range(n-1) 可能遗漏最后一个元素（off-by-one）"
            if isinstance(arg, ast.Name):
                return True, "range(n) 产生 0..n-1，若需要 1..n 请用 range(1, n+1)"
        if len(args) == 2:
            if isinstance(args[0], ast.Constant) and args[0].value == 0:
                if isinstance(args[1], ast.Name):
                    return True, "range(0, n) 等价于 range(n)，如需要包含n请用 range(n+1)"
        return False, ""

    def _is_inside_if(self, node: ast.AST, func: ast.FunctionDef) -> bool:
        for parent in ast.walk(func):
            if isinstance(parent, ast.If):
                for child in ast.walk(parent):
                    if child is node:
                        return True
        return False

    def _max_loop_depth(self, tree: ast.AST) -> int:
        max_depth = 0
        for node in ast.walk(tree):
            if isinstance(node, (ast.For, ast.While)):
                depth = 1
                parent = node
                while hasattr(parent, 'parent'):
                    parent = getattr(parent, 'parent', None)
                    if isinstance(parent, (ast.For, ast.While)):
                        depth += 1
                max_depth = max(max_depth, depth)
        return max_depth

    def _has_list_operations(self, tree: ast.AST) -> bool:
        for node in ast.walk(tree):
            if isinstance(node, ast.Subscript):
                return True
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                if node.func.attr in ("append", "pop", "sort", "insert", "remove"):
                    return True
            if isinstance(node, ast.For):
                return True
        return False

    def _has_empty_check(self, tree: ast.AST) -> bool:
        for node in ast.walk(tree):
            if isinstance(node, ast.If):
                test_str = ast.unparse(node.test) if hasattr(ast, 'unparse') else ""
                if "not" in test_str or "None" in test_str or "len" in test_str:
                    return True
        return False


class ComplexityAnalyzer:
    """Estimate algorithmic complexity from code structure."""

    @staticmethod
    def estimate(code: str) -> str:
        """Heuristic complexity estimation based on loop structure."""
        try:
            tree = ast.parse(code)
        except SyntaxError:
            return "unknown"

        max_depth = 0
        has_divide_and_conquer = False
        has_linear = False

        for node in ast.walk(tree):
            if isinstance(node, (ast.For, ast.While)):
                has_linear = True
                depth = ComplexityAnalyzer._loop_depth(node)
                max_depth = max(max_depth, depth)

        # Check for divide-and-conquer patterns (recursive calls on half input)
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                for arg in node.args:
                    if isinstance(arg, ast.BinOp) and isinstance(arg.op, ast.Div):
                        has_divide_and_conquer = True

        if not has_linear:
            return "O(1)"
        if has_divide_and_conquer:
            return "O(n log n) — 疑似分治法"
        if max_depth == 1:
            return "O(n)"
        if max_depth == 2:
            return "O(n²)"
        return f"O(n^{max_depth})"

    @staticmethod
    def _loop_depth(node, depth=0):
        parent = getattr(node, 'parent', None)
        while parent:
            if isinstance(parent, (ast.For, ast.While)):
                depth += 1
            parent = getattr(parent, 'parent', None)
        return depth
