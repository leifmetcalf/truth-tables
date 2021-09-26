from __future__ import annotations
from enum import Enum
from itertools import chain, groupby
import fileinput
from re import finditer
from typing import NamedTuple

Head = Enum('Head', 'SYMBOL NOT OR AND IMPLIES EQUIV PAREN')

class Expr(NamedTuple):
    head: Head
    value: Any = None
    children: tuple[Expr, ...] = tuple()

def tokenise(s):
    tokens = [
        ('NOT',     r'!|~'),
        ('OR',      r'v|\|'),
        ('AND',     r'\^|&'),
        ('IMPLIES', r'->'),
        ('EQUIV',   r'<->'),
        ('LPAREN',  r'\('),
        ('RPAREN',  r'\)'),
        ('SYMBOL',  r'[a-uw-zA-Z]+'),
        ('EOF',     r'$'),
        ]
    token_pattern = '|'.join(f'(?P<{name}>{pattern})' for name, pattern in tokens)
    return list(reversed(list(finditer(token_pattern, s))))

def try_match(tokens, token):
    if tokens[-1].lastgroup == token:
        return tokens.pop()
    else:
        return None

def match(tokens, token):
    res = try_match(tokens, token)
    if res:
        return res
    else:
        raise Exception(f'Expected {token}')

def parse_1(tokens):
    left = parse_2(tokens)
    while try_match(tokens, 'IMPLIES'):
        left = Expr(Head.IMPLIES, children = (left, parse_2(tokens)))
    return left

def parse_2(tokens):
    left = parse_3(tokens)
    while try_match(tokens, 'EQUIV'):
        left = Expr(Head.EQUIV, children = (left, parse_3(tokens)))
    return left

def parse_3(tokens):
    left = parse_4(tokens)
    while try_match(tokens, 'OR'):
        left = Expr(Head.OR, children = (left, parse_3(tokens)))
    return left

def parse_4(tokens):
    left = parse_5(tokens)
    while try_match(tokens, 'AND'):
        left = Expr(Head.AND, children = (left, parse_3(tokens)))
    return left

def parse_5(tokens):
    if try_match(tokens, 'NOT'):
        return Expr(Head.NOT, children = (parse_5(tokens),))
    elif token := try_match(tokens, 'SYMBOL'):
        return Expr(Head.SYMBOL, value = token.group('SYMBOL'))
    elif try_match(tokens, 'LPAREN'):
        expr = parse_1(tokens)
        match(tokens, 'RPAREN')
        return Expr(Head.PAREN, children = (expr,))
    else:
        raise Exception(f'Unexpected token \'{tokens[-1].lastgroup}\'')

def parse(tokens):
    expr = parse_1(tokens)
    match(tokens, 'EOF')
    return expr

def pretty(expr):
    def go(expr):
        if expr.head == Head.SYMBOL:
            yield expr.value
        elif expr.head == Head.NOT:
            yield r'\neg'
            yield from go(expr.children[0])
        elif expr.head == Head.OR:
            yield from go(expr.children[0])
            for child in expr.children[1:]:
                yield r'\lor'
                yield from go(child)
        elif expr.head == Head.AND:
            yield from go(expr.children[0])
            for child in expr.children[1:]:
                yield r'\land'
                yield from go(child)
        elif expr.head == Head.IMPLIES:
            yield from go(expr.children[0])
            for child in expr.children[1:]:
                yield r'\rightarrow'
                yield from go(child)
        elif expr.head == Head.EQUIV:
            yield from go(expr.children[0])
            for child in expr.children[1:]:
                yield r'\leftrightarrow'
                yield from go(child)
        elif expr.head == Head.PAREN:
            yield '('
            yield from go(expr.children[0])
            yield ')'
    return ' '.join(go(expr))

def flatten(expr):
    if expr.head in {Head.OR, Head.AND}:
        return expr._replace(children = tuple(chain.from_iterable(
            child.children if child.head == expr.head else (child,)
                for child in map(flatten, expr.children)
            )))
    else:
        return expr._replace(children = tuple(map(flatten, expr.children)))

def get_vars(expr):
    def go(expr):
        if expr.head == Head.SYMBOL:
            yield expr.value
        else:
            for child in expr.children:
                yield from go(child)
    return sorted(set(go(expr)))

def eval_expr(expr, env):
    def go(expr):
        return {
            Head.SYMBOL:  lambda: env[expr.value],
            Head.NOT:     lambda: not go(expr.children[0]),
            Head.OR:      lambda: any(map(go, expr.children)),
            Head.AND:     lambda: all(map(go, expr.children)),
            Head.IMPLIES: lambda: not go(expr.children[0]) or go(expr.children[1]),
            Head.EQUIV:   lambda: go(expr.children[0]) == go(expr.children[1]),
            Head.PAREN:   lambda: go(expr.children[0]),
            }[expr.head]()
    return go(expr)

def subexpressions(expr):
    seen = set()
    def go(expr):
        for child in expr.children:
            yield from go(child)
        if expr.head not in {Head.PAREN, Head.SYMBOL} and expr not in seen:
            seen.add(expr)
            yield expr
    return go(expr)

def make_table(exprs, expr_vars):
    envs = [dict()]
    for v in reversed(expr_vars):
        for i in range(len(envs)):
            envs.append(envs[i] | {v: 0})
            envs[i][v] = 1
    table = []
    exprs = list(chain((Expr(Head.SYMBOL, value = v) for v in expr_vars), exprs))
    for env in envs:
        table.append(' & '.join(str(int(eval_expr(expr, env))) for expr in exprs))
    return ''.join((
        '\\begin{tabular}{',
        'c' * len(exprs),
        '}\\toprule\n',
        ' & '.join(f'\\({pretty(expr)}\\)' for expr in exprs),
        '\\\\\\midrule\n',
        '\\\\\n'.join(table),
        '\\\\\\bottomrule\n\\end{tabular}'))

for s in fileinput.input():
    expr = flatten(parse(tokenise(s)))
    print(make_table(subexpressions(expr), get_vars(expr)))
