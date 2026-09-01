"""
Project:   edgestream-api
File:      edgestream/services/vrl_parser.py
Language:  Python

License:   BUSL-1.1
Copyright: (c) 2026 HYPERI PTY LIMITED
"""

from __future__ import annotations
from typing import Any, Dict, List, Union

OPERATOR_MAPPING = {
    'equal': '==',
    '=': '==',
    'not_equal': '!=',
    '!=': '!=',
    'less': '<',
    '<': '<',
    'less_or_equal': '<=',
    '<=': '<=',
    'greater': '>',
    '>': '>',
    'greater_or_equal': '>=',
    '>=': '>='
}


def parse_rule(rule: Dict[str, Any]) -> str:
    """
    Converts a single atomic rule into a string condition.
    Example: {'field': 'severity', 'operator': 'greater', 'value': 3} 
    becomes ".severity > 3"
    """
    field = rule.get('field', '')
    raw_op = rule.get('operator')
    operator = OPERATOR_MAPPING.get(raw_op, '==')
    value = rule.get('value', '')

    if isinstance(value, str):
        clean_value = value.replace('"', '\\"')
        value = f'"{clean_value}"'
    elif value is None:
        value = 'null'

    return f".{field} {operator} {value}"


def parse_condition(condition: Dict[str, Any]) -> str:
    """
    Recursively processes nested rule sets and combines them using 
    logical AND (&&) or OR (||) symbols.
    """
    rules = condition.get('rules', [])
    combinator = str(condition.get('combinator', 'AND')).upper()

    operator_symbol = '&&' if combinator == 'AND' else '||'

    parsed_parts: List[str] = []

    for rule in rules:
        if 'rules' in rule:
            nested_expression = parse_condition(rule)
            if nested_expression:
                parsed_parts.append(f"({nested_expression})")
        else:
            parsed_parts.append(parse_rule(rule))

    return f" {operator_symbol} ".join(parsed_parts)
