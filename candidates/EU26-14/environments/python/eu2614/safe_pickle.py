"""A small protocol-5 parser for the frozen NumPy result pickle.

This module never invokes a general unpickler, imports a named pickle global,
or executes a callable from the payload. ``REDUCE`` and ``BUILD`` are treated
as syntax: only the two exact NumPy encodings emitted by the frozen file are
recognized and converted by local code.
"""

from __future__ import annotations

import math
import pickletools
import struct
from collections import Counter
from dataclasses import dataclass
from typing import Any

from .errors import VerificationError


MAX_PAYLOAD_BYTES = 1_000_000
MAX_MEMO_ITEMS = 10_000
MAX_STACK_ITEMS = 200_000
MAX_CONTAINER_ITEMS = 100_000
MAX_ARRAY_ITEMS = 100_000

_ALLOWED_GLOBALS = {
    ("numpy._core.numeric", "_frombuffer"),
    ("numpy", "dtype"),
}
_ALLOWED_OPCODES = {
    "PROTO",
    "FRAME",
    "EMPTY_DICT",
    "EMPTY_LIST",
    "MARK",
    "SHORT_BINUNICODE",
    "BININT1",
    "BININT2",
    "BININT",
    "BINFLOAT",
    "NONE",
    "NEWTRUE",
    "NEWFALSE",
    "BYTEARRAY8",
    "MEMOIZE",
    "BINGET",
    "LONG_BINGET",
    "TUPLE",
    "TUPLE1",
    "TUPLE2",
    "TUPLE3",
    "APPENDS",
    "SETITEMS",
    "STACK_GLOBAL",
    "REDUCE",
    "BUILD",
    "STOP",
}


@dataclass(frozen=True)
class ArrayValue:
    """An immutable, locally decoded NumPy array representation."""

    dtype: str
    shape: tuple[int, ...]
    values: tuple[int | float, ...]

    def row(self, index: int) -> tuple[int | float, ...]:
        if len(self.shape) != 2:
            raise VerificationError("row access requires a two-dimensional array")
        rows, columns = self.shape
        normalized = index if index >= 0 else rows + index
        if not 0 <= normalized < rows:
            raise VerificationError("array row index out of bounds")
        start = normalized * columns
        return self.values[start : start + columns]

    def scalar(self, index: int) -> int | float:
        if len(self.shape) != 1:
            raise VerificationError("scalar access requires a one-dimensional array")
        return self.values[index]


@dataclass(frozen=True)
class ParseResult:
    value: Any
    opcode_counts: dict[str, int]
    symbolic_globals: tuple[str, ...]


@dataclass(frozen=True)
class _Symbol:
    module: str
    name: str


@dataclass
class _DType:
    code: str
    built: bool = False
    byte_order: str | None = None


class _Mark:
    pass


_MARK = _Mark()


def _is_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _pop_mark(stack: list[Any]) -> list[Any]:
    for index in range(len(stack) - 1, -1, -1):
        if stack[index] is _MARK:
            values = stack[index + 1 :]
            del stack[index:]
            return values
    raise VerificationError("pickle stack has no matching MARK")


def _validate_dtype_reduce(arguments: Any) -> _DType:
    if not isinstance(arguments, tuple) or len(arguments) != 3:
        raise VerificationError("numpy.dtype REDUCE arguments differ")
    code, align, copy = arguments
    if code not in {"i8", "f8"} or align is not False or copy is not True:
        raise VerificationError("numpy.dtype REDUCE form is not admitted")
    return _DType(code=code)


def _validate_dtype_build(instance: Any, state: Any) -> _DType:
    if not isinstance(instance, _DType) or instance.built:
        raise VerificationError("BUILD target is not a fresh admitted dtype")
    if (
        not isinstance(state, tuple)
        or len(state) != 8
        or not _is_int(state[0])
        or state[0] != 3
        or not isinstance(state[1], str)
        or state[1] != "<"
        or any(item is not None for item in state[2:5])
        or any(not _is_int(item) for item in state[5:8])
        or state[5:] != (-1, -1, 0)
    ):
        raise VerificationError("numpy.dtype BUILD state differs")
    instance.built = True
    instance.byte_order = "<"
    return instance


def _decode_array(arguments: Any) -> ArrayValue:
    if not isinstance(arguments, tuple) or len(arguments) != 4:
        raise VerificationError("_frombuffer REDUCE arguments differ")
    buffer, dtype, shape, order = arguments
    if not isinstance(buffer, bytes):
        raise VerificationError("_frombuffer input is not an immutable byte buffer")
    if not isinstance(dtype, _DType) or not dtype.built or dtype.byte_order != "<":
        raise VerificationError("_frombuffer dtype is not admitted")
    if not isinstance(shape, tuple) or not 1 <= len(shape) <= 3:
        raise VerificationError("array shape differs")
    if any(not _is_int(item) or item <= 0 for item in shape):
        raise VerificationError("array shape contains an invalid dimension")
    if order != "C":
        raise VerificationError("only C-order arrays are admitted")
    count = math.prod(shape)
    if count > MAX_ARRAY_ITEMS or len(buffer) != count * 8:
        raise VerificationError("array byte count differs from shape and dtype")
    format_code = "q" if dtype.code == "i8" else "d"
    values = tuple(item[0] for item in struct.iter_unpack("<" + format_code, buffer))
    if dtype.code == "f8" and any(not math.isfinite(item) for item in values):
        raise VerificationError("numeric array contains a non-finite value")
    return ArrayValue(dtype=dtype.code, shape=shape, values=values)


def _reduce(function: Any, arguments: Any) -> Any:
    if not isinstance(function, _Symbol):
        raise VerificationError("REDUCE callable is not an admitted symbol")
    identity = (function.module, function.name)
    if identity == ("numpy", "dtype"):
        return _validate_dtype_reduce(arguments)
    if identity == ("numpy._core.numeric", "_frombuffer"):
        return _decode_array(arguments)
    raise VerificationError("REDUCE symbol is not admitted")


def parse_numpy_pickle(payload: bytes) -> ParseResult:
    """Parse the frozen primitive/NumPy subset without executing pickle code."""
    if not isinstance(payload, bytes) or not 1 <= len(payload) <= MAX_PAYLOAD_BYTES:
        raise VerificationError("pickle payload size is outside the admitted range")
    stack: list[Any] = []
    memo: dict[int, Any] = {}
    counts: Counter[str] = Counter()
    globals_seen: list[str] = []
    saw_proto = False
    stop_position: int | None = None

    try:
        operations = pickletools.genops(payload)
        for opcode, argument, position in operations:
            name = opcode.name
            counts[name] += 1
            if name not in _ALLOWED_OPCODES:
                raise VerificationError(f"pickle opcode {name} is not admitted")
            if name == "PROTO":
                if saw_proto or position != 0 or argument != 5:
                    raise VerificationError("pickle must begin with protocol 5")
                saw_proto = True
            elif name == "FRAME":
                if not saw_proto or not _is_int(argument) or argument <= 0:
                    raise VerificationError("pickle FRAME differs")
            elif name == "EMPTY_DICT":
                stack.append({})
            elif name == "EMPTY_LIST":
                stack.append([])
            elif name == "MARK":
                stack.append(_MARK)
            elif name == "SHORT_BINUNICODE":
                if not isinstance(argument, str) or len(argument) > 10_000:
                    raise VerificationError("pickle string differs")
                stack.append(argument)
            elif name in {"BININT1", "BININT2", "BININT"}:
                if not _is_int(argument):
                    raise VerificationError("pickle integer differs")
                stack.append(argument)
            elif name == "BINFLOAT":
                if not isinstance(argument, float) or math.isnan(argument):
                    raise VerificationError("pickle float is invalid")
                stack.append(argument)
            elif name == "NONE":
                stack.append(None)
            elif name == "NEWTRUE":
                stack.append(True)
            elif name == "NEWFALSE":
                stack.append(False)
            elif name == "BYTEARRAY8":
                buffer = bytes(argument)
                if len(buffer) > MAX_PAYLOAD_BYTES:
                    raise VerificationError("pickle byte buffer is too large")
                stack.append(buffer)
            elif name == "MEMOIZE":
                if not stack or len(memo) >= MAX_MEMO_ITEMS:
                    raise VerificationError("pickle memo limit exceeded")
                memo[len(memo)] = stack[-1]
            elif name in {"BINGET", "LONG_BINGET"}:
                if argument not in memo:
                    raise VerificationError("pickle memo reference is invalid")
                stack.append(memo[argument])
            elif name == "TUPLE":
                stack.append(tuple(_pop_mark(stack)))
            elif name == "TUPLE1":
                if len(stack) < 1:
                    raise VerificationError("pickle TUPLE1 underflow")
                stack[-1:] = [(stack[-1],)]
            elif name == "TUPLE2":
                if len(stack) < 2:
                    raise VerificationError("pickle TUPLE2 underflow")
                stack[-2:] = [(stack[-2], stack[-1])]
            elif name == "TUPLE3":
                if len(stack) < 3:
                    raise VerificationError("pickle TUPLE3 underflow")
                stack[-3:] = [(stack[-3], stack[-2], stack[-1])]
            elif name == "APPENDS":
                values = _pop_mark(stack)
                if not stack or not isinstance(stack[-1], list):
                    raise VerificationError("APPENDS target is not a list")
                if len(stack[-1]) + len(values) > MAX_CONTAINER_ITEMS:
                    raise VerificationError("pickle list limit exceeded")
                stack[-1].extend(values)
            elif name == "SETITEMS":
                values = _pop_mark(stack)
                if not stack or not isinstance(stack[-1], dict) or len(values) % 2:
                    raise VerificationError("SETITEMS form differs")
                mapping = stack[-1]
                if len(mapping) + len(values) // 2 > MAX_CONTAINER_ITEMS:
                    raise VerificationError("pickle mapping limit exceeded")
                for index in range(0, len(values), 2):
                    key, value = values[index], values[index + 1]
                    if not isinstance(key, (str, int)) or isinstance(key, bool):
                        raise VerificationError("pickle mapping key type differs")
                    if key in mapping:
                        raise VerificationError("pickle mapping has a duplicate key")
                    mapping[key] = value
            elif name == "STACK_GLOBAL":
                if len(stack) < 2:
                    raise VerificationError("STACK_GLOBAL underflow")
                module, symbol = stack[-2], stack[-1]
                if not isinstance(module, str) or not isinstance(symbol, str):
                    raise VerificationError("STACK_GLOBAL names differ")
                if (module, symbol) not in _ALLOWED_GLOBALS:
                    raise VerificationError(f"pickle global {module}.{symbol} is not admitted")
                stack[-2:] = [_Symbol(module=module, name=symbol)]
                globals_seen.append(f"{module}.{symbol}")
            elif name == "REDUCE":
                if len(stack) < 2:
                    raise VerificationError("REDUCE underflow")
                function, arguments = stack[-2], stack[-1]
                stack[-2:] = [_reduce(function, arguments)]
            elif name == "BUILD":
                if len(stack) < 2:
                    raise VerificationError("BUILD underflow")
                instance, state = stack[-2], stack[-1]
                stack[-2:] = [_validate_dtype_build(instance, state)]
            elif name == "STOP":
                if len(stack) != 1 or stack[0] is _MARK:
                    raise VerificationError("pickle STOP stack differs")
                stop_position = position
                break
            if len(stack) > MAX_STACK_ITEMS:
                raise VerificationError("pickle stack limit exceeded")
    except VerificationError:
        raise
    except (ValueError, IndexError, OverflowError, struct.error) as error:
        raise VerificationError(f"malformed pickle syntax: {error}") from error

    if not saw_proto or stop_position is None or stop_position + 1 != len(payload):
        raise VerificationError("pickle is incomplete or has trailing bytes")
    expected_globals = (
        "numpy._core.numeric._frombuffer",
        "numpy.dtype",
    )
    if tuple(globals_seen) != expected_globals:
        raise VerificationError("pickle symbolic-global sequence differs")
    return ParseResult(
        value=stack[0],
        opcode_counts=dict(sorted(counts.items())),
        symbolic_globals=tuple(globals_seen),
    )
