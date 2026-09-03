"""
skills/math_solver_skill.py
------------------------------------------------------------
Math & Logic Solver - equations solve karna, expressions evaluate
karna, aur pure-reasoning/logic waale sawaal LLM se solve karwana.

Equation/expression solving ke liye SymPy use hota hai (exact,
step-by-step-capable, calculator se zyada reliable) - isliye
requirements-optional.txt mein `sympy` add kiya gaya hai:
    pip install sympy

Agar sympy install nahi hai to bhi crash nahi hoga - clear error
milega ("pip install sympy karo").

General logic/reasoning puzzles (jaise "agar A, B se bada hai...")
ke liye seedha general_chat action use karo (LLM khud reasoning kar
lega) - is skill ka use sirf tab karo jab ek CONCRETE equation ya
expression solve/evaluate karna ho.
"""

import re

try:
    import sympy
    from sympy.parsing.sympy_parser import (
        parse_expr,
        standard_transformations,
        implicit_multiplication_application,
        convert_xor,
    )
    _SYMPY_OK = True
except ImportError:
    _SYMPY_OK = False

_TRANSFORMS = None
if _SYMPY_OK:
    _TRANSFORMS = standard_transformations + (
        implicit_multiplication_application,
        convert_xor,
    )


def _clean(expr: str) -> str:
    """Common human-typed symbols ko SymPy-friendly banata hai."""
    expr = expr.replace("^", "**")
    expr = expr.replace("×", "*").replace("÷", "/")
    return expr.strip()


def solve_equation(params: dict) -> str:
    """Ek ya zyada equations solve karta hai (variable ke liye).
    Example: "2x + 5 = 15" -> x = 5"""
    if not _SYMPY_OK:
        return "SymPy install nahi hai. Chalao: pip install sympy"
    equation = params.get("equation", "").strip()
    variable = params.get("variable", "x").strip() or "x"
    if not equation:
        return "Kaunsa equation solve karna hai, batao."
    try:
        equation = _clean(equation)
        if "=" in equation:
            lhs, rhs = equation.split("=", 1)
        else:
            lhs, rhs = equation, "0"
        sym = sympy.symbols(variable)
        lhs_expr = parse_expr(lhs, transformations=_TRANSFORMS)
        rhs_expr = parse_expr(rhs, transformations=_TRANSFORMS)
        solutions = sympy.solve(sympy.Eq(lhs_expr, rhs_expr), sym)
        if not solutions:
            return f"'{equation}' ka koi solution nahi mila (ya galat likha gaya hoga)."
        sol_text = ", ".join(str(s) for s in solutions)
        return f"{variable} = {sol_text}"
    except Exception as e:
        return f"Equation samajh nahi aaya ya solve nahi hua: {e}"


def evaluate_expression(params: dict) -> str:
    """Koi bhi numeric expression evaluate karta hai - jaise
    "12 * (3 + 4) / 2", "sqrt(144)", "sin(30 degrees)" jaisa kuch."""
    if not _SYMPY_OK:
        return "SymPy install nahi hai. Chalao: pip install sympy"
    expression = params.get("expression", "").strip()
    if not expression:
        return "Kaunsa expression calculate karna hai, batao."
    try:
        expression = _clean(expression)
        result = sympy.N(parse_expr(expression, transformations=_TRANSFORMS))
        return f"{expression} = {result}"
    except Exception as e:
        return f"Expression evaluate nahi ho saka: {e}"


def simplify_expression(params: dict) -> str:
    """Algebra expression simplify/factor karta hai."""
    if not _SYMPY_OK:
        return "SymPy install nahi hai. Chalao: pip install sympy"
    expression = params.get("expression", "").strip()
    if not expression:
        return "Kaunsa expression simplify karna hai, batao."
    try:
        expression = _clean(expression)
        expr = parse_expr(expression, transformations=_TRANSFORMS)
        simplified = sympy.simplify(expr)
        return f"Simplified: {simplified}"
    except Exception as e:
        return f"Simplify nahi ho saka: {e}"


ACTIONS = {
    "solve_equation": solve_equation,
    "evaluate_expression": evaluate_expression,
    "simplify_expression": simplify_expression,
}

DOCS = """
- solve_equation: {"equation": "2x + 5 = 15", "variable": "x"}
    (equation ko variable ke liye solve karta hai, variable optional - default x)
- evaluate_expression: {"expression": "12 * (3 + 4) / 2"}
    (numeric expression calculate karta hai - sqrt, sin, cos, log, etc. bhi chalte hain)
- simplify_expression: {"expression": "(x**2 - 1)/(x - 1)"}
    (algebra expression simplify/factor karta hai)

IMPORTANT - PURE LOGIC/REASONING puzzle ho (koi equation na ho, jaise
"agar sab A hain to kuch B hain kya"), to inn actions ka use MAT karo -
uske liye general_chat use karo, LLM khud reasoning kar dega.

Example:
User: "2x + 5 = 15 solve karo"
-> {"actions": [{"action": "solve_equation", "params": {"equation": "2x + 5 = 15", "variable": "x"}}]}

User: "12 into 3 plus 4, divide by 2 kitna hoga"
-> {"actions": [{"action": "evaluate_expression", "params": {"expression": "12 * (3 + 4) / 2"}}]}
"""
