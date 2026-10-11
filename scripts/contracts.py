"""Shared strict JSON and validation primitives; no I/O or network at import."""
from __future__ import annotations
import hashlib
import json
import math
import re
from typing import Any

MAX_FILE_BYTES = 1_048_576
MAX_JSON_DEPTH = 64
MAX_INTEGER_DIGITS = 128

class HikmahError(ValueError):
    """An actionable validation, verification, or safe-output error."""


def require(condition: bool, message: str) -> None:
    if not condition:
        raise HikmahError(message)


def exact_keys(value: Any, keys: set[str], label: str) -> None:
    require(isinstance(value, dict) and set(value) == keys,
            f'{label} must contain exactly: {", ".join(sorted(keys))}')


def text(value: Any, label: str, maximum: int = 1024) -> None:
    require(isinstance(value, str) and bool(value.strip()), f'{label} must be a non-empty string')
    require(len(value) <= maximum and not any(ord(c) < 32 or 0xD800 <= ord(c) <= 0xDFFF for c in value),
            f'{label} must be single-line valid Unicode of at most {maximum} characters')


def _pairs(items: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in items:
        require(key not in result, f'duplicate JSON key: {key}')
        result[key] = value
    return result


def _constant(_: str) -> None:
    raise HikmahError('non-finite JSON numbers are not allowed')


def _float(value: str) -> float:
    result = float(value)
    require(math.isfinite(result), 'non-finite JSON numbers are not allowed')
    return result


def _integer(value: str) -> int:
    require(len(value.lstrip('-')) <= MAX_INTEGER_DIGITS, 'JSON integer is excessively large')
    return int(value)


def decode_json(raw: str, label: str, limit: int = MAX_FILE_BYTES) -> Any:
    require(type(limit) is int and 0 < limit <= 1024 * MAX_FILE_BYTES, 'JSON size limit must be a bounded integer')
    require(len(raw) <= limit, f'{label}: JSON is too large')
    try:
        value = json.loads(raw, object_pairs_hook=_pairs, parse_constant=_constant,
                           parse_float=_float, parse_int=_integer)
        pending = [(value, 0)]
        while pending:
            item, depth = pending.pop()
            require(depth <= MAX_JSON_DEPTH, f'{label}: JSON nesting is excessively deep')
            if isinstance(item, dict):
                pending.extend((child, depth + 1) for child in item.values())
            elif isinstance(item, list):
                pending.extend((child, depth + 1) for child in item)
        return value
    except HikmahError:
        raise
    except (ValueError, RecursionError) as exc:
        raise HikmahError(f'{label}: invalid or excessively complex JSON') from exc


def json_bytes(value: Any) -> bytes:
    return (json.dumps(value, indent=2, ensure_ascii=False, sort_keys=True, allow_nan=False) + '\n').encode('utf-8')


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def fingerprint(files: dict[str, bytes]) -> str:
    return digest(json_bytes({name: digest(data) for name, data in sorted(files.items())}))



def parse_frontmatter(raw: str, label: str) -> tuple[dict[str, Any], str]:
    """Accept the project's safe YAML subset: key: JSON-literal, one field per line."""
    lines = raw.splitlines()
    require(bool(lines) and lines[0] == '---', f'{label}: missing frontmatter')
    try:
        end = lines.index('---', 1)
    except ValueError as exc:
        raise HikmahError(f'{label}: unclosed frontmatter') from exc
    values: dict[str, Any] = {}
    for line in lines[1:end]:
        key, separator, value = line.partition(':')
        require(bool(separator) and bool(re.fullmatch(r'[a-z][a-z_]*', key)),
                f'{label}: use key: JSON-value frontmatter')
        require(key not in values, f'{label}: duplicate frontmatter key {key}')
        values[key] = decode_json(value.strip(), f'{label}: {key}')
    body = '\n'.join(lines[end + 1:]).strip() + '\n'
    require(bool(body.strip()), f'{label}: empty body')
    return values, body

