import ast
import math
import operator
import random
import statistics
from typing import Any, Dict, Optional


class EvalError(Exception):
    pass


class SafeEvaluator(ast.NodeVisitor):
    """
    Evaluates a parsed AST expression safely, allowing only a small set of nodes,
    functions and operators.
    """

    def __init__(self, funcs: Dict[str, Any], names: Dict[str, Any]):
        self.funcs = funcs
        self.names = names

    def visit(self, node):
        method = "visit_" + node.__class__.__name__
        visitor = getattr(self, method, self.generic_visit)
        return visitor(node)

    def visit_Expression(self, node: ast.Expression):
        return self.visit(node.body)

    def visit_Constant(self, node: ast.Constant):
        return node.value

    # For older Python versions where Num/Str/NameConstant used
    def visit_Num(self, node: ast.Num):
        return node.n

    def visit_UnaryOp(self, node: ast.UnaryOp):
        operand = self.visit(node.operand)
        if isinstance(node.op, ast.UAdd):
            return +operand
        if isinstance(node.op, ast.USub):
            return -operand
        if isinstance(node.op, ast.Not):
            return not operand
        raise EvalError(f"Unsupported unary operator: {node.op}")

    def visit_BinOp(self, node: ast.BinOp):
        left = self.visit(node.left)
        right = self.visit(node.right)
        op = node.op
        ops = {
            ast.Add: operator.add,
            ast.Sub: operator.sub,
            ast.Mult: operator.mul,
            ast.Div: operator.truediv,
            ast.FloorDiv: operator.floordiv,
            ast.Mod: operator.mod,
            ast.Pow: operator.pow,
        }
        for t, fn in ops.items():
            if isinstance(op, t):
                try:
                    return fn(left, right)
                except ZeroDivisionError:
                    raise EvalError("Division by zero")
                except Exception as e:
                    raise EvalError(str(e))
        raise EvalError(f"Unsupported binary operator: {op}")

    def visit_BoolOp(self, node: ast.BoolOp):
        vals = [self.visit(v) for v in node.values]
        if isinstance(node.op, ast.And):
            return all(vals)
        if isinstance(node.op, ast.Or):
            return any(vals)
        raise EvalError("Unsupported boolean operator")

    def visit_Compare(self, node: ast.Compare):
        left = self.visit(node.left)
        result = True
        for op, comparator in zip(node.ops, node.comparators):
            right = self.visit(comparator)
            if isinstance(op, ast.Eq):
                result = result and (left == right)
            elif isinstance(op, ast.NotEq):
                result = result and (left != right)
            elif isinstance(op, ast.Lt):
                result = result and (left < right)
            elif isinstance(op, ast.LtE):
                result = result and (left <= right)
            elif isinstance(op, ast.Gt):
                result = result and (left > right)
            elif isinstance(op, ast.GtE):
                result = result and (left >= right)
            else:
                raise EvalError("Unsupported comparison")
            left = right
        return result

    def visit_Call(self, node: ast.Call):
        if isinstance(node.func, ast.Name):
            fname = node.func.id.lower()
            if fname not in self.funcs:
                raise EvalError(f"Unknown function: {fname}")
            fn = self.funcs[fname]
            args = [self.visit(a) for a in node.args]
            # keyword args not supported
            try:
                return fn(*args)
            except TypeError as e:
                raise EvalError(f"Function call error: {e}")
            except Exception as e:
                raise EvalError(str(e))
        else:
            raise EvalError("Only direct function calls allowed")

    def visit_Name(self, node: ast.Name):
        nid = node.id.lower()
        if nid in self.names:
            return self.names[nid]
        raise EvalError(f"Unknown name: {node.id}")

    def visit_List(self, node: ast.List):
        return [self.visit(elt) for elt in node.elts]

    def visit_Tuple(self, node: ast.Tuple):
        return tuple(self.visit(elt) for elt in node.elts)

    def generic_visit(self, node):
        raise EvalError(f"Unsupported expression: {node.__class__.__name__}")


class CalculatorEngine:
    def __init__(self):
        self.mode = "deg"  # "deg" or "rad"

    def set_mode(self, mode: str):
        if mode in ("deg", "rad"):
            self.mode = mode

    def _angle_wrapper(self, trig_fn):
        # Return a wrapper that applies angle conversion based on mode
        if self.mode == "rad":
            return lambda x: trig_fn(x)
        return lambda x: trig_fn(math.radians(x))

    def _prepare_functions(self):
        # math and helper functions exposed to the evaluator.
        funcs = {
            # trig (mode-aware)
            "sin": self._angle_wrapper(math.sin),
            "cos": self._angle_wrapper(math.cos),
            "tan": self._angle_wrapper(math.tan),
            "sec": lambda x: 1 / self._angle_wrapper(math.cos)(x),
            "csc": lambda x: 1 / self._angle_wrapper(math.sin)(x),
            "cot": lambda x: 1 / self._angle_wrapper(math.tan)(x),

            # logs & roots
            "sqrt": math.sqrt,
            "log": lambda *a: math.log10(a[0]) if len(a) == 1 else math.log(a[0], a[1]),
            "ln": math.log,

            # statistics and utils
            "mean": lambda *a: statistics.mean(a) if len(a) >= 1 else EvalError("mean() needs args"),
            "median": lambda *a: statistics.median(a),
            "mode": lambda *a: self._safe_mode(a),
            "std": lambda *a: statistics.stdev(a) if len(a) > 1 else (_raise("Need ≥2 values for stdev")),
            "stdev": lambda *a: statistics.stdev(a) if len(a) > 1 else (_raise("Need ≥2 values for stdev")),
            "variance": lambda *a: statistics.variance(a) if len(a) > 1 else (_raise("Need ≥2 values for variance")),

            "min": lambda *a: min(a),
            "max": lambda *a: max(a),
            "abs": abs,
            "round": round,
            "factorial": lambda n: math.factorial(int(n)),
            "mod": lambda a, b: a % b,

            # randomness
            "rand": lambda: random.random(),
            "choice": lambda *a: random.choice(a[0]) if len(a) == 1 and isinstance(a[0], (list, tuple)) else (_raise("choice requires a single sequence argument")),
        }

        return funcs

    def _prepare_names(self, extra: Optional[Dict[str, Any]] = None):
        names = {
            "pi": math.pi,
            "e": math.e,
        }
        if extra:
            for k, v in extra.items():
                names[k.lower()] = v
        return names

    @staticmethod
    def _safe_mode(args):
        try:
            return statistics.mode(list(args))
        except statistics.StatisticsError:
            return "No unique mode"

    def calculate(self, expression: str):
        """
        Calculate an expression string. Uses AST-based evaluation for safety.
        Supports functions like mean(1,2,3), sin(30), arithmetic, lists, etc.
        """
        try:
            if not isinstance(expression, str):
                raise EvalError("Expression must be a string")

            expr = expression.replace(" ", "").replace("^", "**")

            # parse
            node = ast.parse(expr, mode="eval")
            funcs = self._prepare_functions()
            names = self._prepare_names()
            evaluator = SafeEvaluator(funcs, names)
            result = evaluator.visit(node)

            return result
        except EvalError as e:
            return f"Error: {e}"
        except ZeroDivisionError:
            return "Division by zero"
        except Exception:
            return "Error"

    def evaluate_for_x(self, expression: str, x_value: float):
        """
        Evaluate expression containing variable 'x'. Uses same safe evaluator and mode rules.
        Example: evaluate_for_x("2*x + sin(x)", 3.14)
        """
        try:
            if not isinstance(expression, str):
                raise EvalError("Expression must be a string")

            expr = expression.replace(" ", "").replace("^", "**")
            node = ast.parse(expr, mode="eval")
            funcs = self._prepare_functions()
            names = self._prepare_names({"x": x_value})
            evaluator = SafeEvaluator(funcs, names)
            return evaluator.visit(node)
        except EvalError:
            return None
        except Exception:
            return None


def _raise(msg):
    raise EvalError(msg)


# Quick local demo
if __name__ == "__main__":
    c = CalculatorEngine()
    print(c.calculate("mean(1,2,3)"))
    print(c.calculate("sin(30)"))  # default deg -> 0.5
    c.set_mode("rad")
    print(c.calculate("sin(pi/2)"))  # rad mode
    print(c.evaluate_for_x("2*x + sin(x)", 3.14))