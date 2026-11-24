"""Encode written expressions and their ordered tree contexts."""

import ast


UNARY = ('sin', 'cos', 'exp', 'log', 'asin', 'abs')
BINARY = ('+', '*', '/', '^')
ARITHMETIC = {ast.Add: '+', ast.Mult: '*', ast.Div: '/', ast.Pow: '^'}
ALIASES = {'ln': 'log', 'Abs': 'abs', 'arcsin': 'asin'}
P, N, HALF, TWO, ONE = '^', '@-1', '@0.5', '@2', '@1'

def normalized_tree(formula):
    """Translate written RHS syntax without SymPy simplification or commutation."""
    def number(value):
        return (f'@{value}',)

    def negate(child):
        if child[0].startswith('@'):
            value = child[0][1:]
            return ('@' + (value[1:] if value.startswith('-') else '-' + value),)
        return ('*', (N,), child)

    def translate(node):
        if isinstance(node, ast.Name):
            return (node.id,)
        if isinstance(node, ast.Constant) and type(node.value) in (int, float):
            return number(node.value)
        if isinstance(node, ast.UnaryOp):
            child = translate(node.operand)
            if isinstance(node.op, ast.USub):
                return negate(child)
            if isinstance(node.op, ast.UAdd):
                return child
        if isinstance(node, ast.BinOp):
            left, right = translate(node.left), translate(node.right)
            op = type(node.op)
            if op is ast.Sub:
                return ('+', left, negate(right))
            if op in ARITHMETIC:
                return (ARITHMETIC[op], left, right)
        if (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                and len(node.args) == 1 and not node.keywords):
            fun = ALIASES.get(node.func.id, node.func.id)
            child = translate(node.args[0])
            if fun in UNARY:
                return (fun, child)
            if fun == 'sqrt':
                return (P, child, (HALF,))
            if fun == 'tan':
                return ('/', ('sin', child), ('cos', child))
            if fun == 'tanh':
                exp = ('exp', ('*', (TWO,), child))
                return ('/', ('+', exp, (N,)), ('+', exp, (ONE,)))
        raise ValueError(f'Unsupported syntax {ast.dump(node)} in {formula}')

    return translate(ast.parse(formula, mode='eval').body)


def prefix_labels(tree):
    """Retain equality of leaves within a tree, while hiding their actual names."""
    leaves = {}

    def visit(node):
        label, *children = node
        if not children:
            yield leaves.setdefault(label, f'x{len(leaves)}')
        else:
            yield label
        for child in children:
            yield from visit(child)

    return list(visit(tree))


def tree_events(prefix):
    """Yield side, shallow context, token and deeper context for each tree node."""
    operators = (*BINARY, *UNARY)
    nodes = iter(prefix)

    def visit(label, ancestors, depth, sibling=None):
        word = label if label in operators else 'x'
        if sibling is None:
            side, context = 'left', ancestors[-2:]
            ancestor = ancestors[-3] if len(ancestors) >= 3 else 'None'
        else:
            sibling_type = sibling if sibling in operators else 'x'
            if word == sibling_type == 'x' and label != sibling:
                word = 'y'
            side, context = 'right', (ancestors[-1], sibling_type)
            ancestor = ancestors[-2]
        yield (side, context, (min(depth, 4), ancestor)), word
        if label in operators:
            left = next(nodes)
            yield from visit(left, (*ancestors, label), depth + 1)
            if label in BINARY:
                yield from visit(next(nodes), (*ancestors, label), depth + 1, left)

    events = list(visit(next(nodes), ('None', 'None'), 0))
    if next(nodes, None) is not None:
        raise ValueError(f'Invalid prefix tree: {prefix}')
    return events
