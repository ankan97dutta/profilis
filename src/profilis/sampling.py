"""Shared sampling policy: global rate, route excludes (prefix/regex), per-route overrides, always 5xx.

Used by ASGI middleware and Sanic adapter for deterministic tests (seedable RNG)
and consistent behavior across adapters.
"""

from __future__ import annotations

import re
import typing as t
from random import Random, random
from typing import cast

# Prefix for regex patterns in route_excludes and route_overrides
REGEX_PREFIX = "re:"
HTTP_ERROR_STATUS_THRESHOLD = 500


def _compile_excludes(excludes: t.Iterable[str]) -> list[tuple[str, t.Union[str, re.Pattern[str]]]]:
    """Compile route_excludes into (type, pattern) list. type is 'prefix' or 'regex'."""
    result: list[tuple[str, t.Union[str, re.Pattern[str]]]] = []
    for pat in excludes or []:
        if not pat:
            continue
        if pat.startswith(REGEX_PREFIX):
            try:
                result.append(("regex", re.compile(pat[len(REGEX_PREFIX) :])))
            except re.error:
                # invalid regex: treat as literal prefix
                result.append(("prefix", pat))
        else:
            result.append(("prefix", pat))
    return result


def should_exclude_route(
    path: str, compiled: list[tuple[str, t.Union[str, re.Pattern[str]]]]
) -> bool:
    """Return True if path matches any exclude (prefix or regex)."""
    for kind, pattern in compiled:
        if kind == "prefix":
            assert isinstance(pattern, str)
            if path.startswith(pattern) or path == pattern:
                return True
        elif kind == "regex":
            if cast(re.Pattern[str], pattern).search(path):
                return True
    return False


def _compile_overrides(
    overrides: t.Iterable[tuple[str, float]] | None,
) -> list[tuple[str, t.Union[str, re.Pattern[str]], float]]:
    """Compile route_overrides into (type, pattern, rate) list."""
    result: list[tuple[str, t.Union[str, re.Pattern[str]], float]] = []
    for pat, rate in overrides or []:
        if not pat:
            continue
        r = float(rate)
        if not 0.0 <= r <= 1.0:
            continue
        if pat.startswith(REGEX_PREFIX):
            try:
                result.append(("regex", re.compile(pat[len(REGEX_PREFIX) :]), r))
            except re.error:
                result.append(("prefix", pat, r))
        else:
            result.append(("prefix", pat, r))
    return result


def get_effective_rate(
    path: str,
    compiled_overrides: list[tuple[str, t.Union[str, re.Pattern[str]], float]],
    default_rate: float,
) -> float:
    """Return sampling rate for path: first matching override, or default_rate."""
    for kind, pattern, rate in compiled_overrides:
        if kind == "prefix":
            assert isinstance(pattern, str)
            if path.startswith(pattern) or path == pattern:
                return rate
        elif kind == "regex":
            if cast(re.Pattern[str], pattern).search(path):
                return rate
    return default_rate


def should_sample_request(rate: float, rng: t.Callable[[], float]) -> bool:
    """Return True if this request should be sampled according to rate and RNG."""
    if rate >= 1.0:
        return True
    if rate <= 0.0:
        return False
    return rng() <= rate


def should_record_request(
    sampled: bool,
    status_code: int | None,
    error_info: dict[str, str] | None,
    always_sample_errors: bool,
    error_threshold: int = HTTP_ERROR_STATUS_THRESHOLD,
) -> bool:
    """Return True if request should be recorded (sampled or 5xx/exception when always_sample_errors)."""
    sc = int(status_code or 0)
    is_error_status = sc >= error_threshold
    return sampled or (always_sample_errors and (error_info is not None or is_error_status))


def make_rng(
    random_seed: int | None = None,
    rng: t.Callable[[], float] | None = None,
) -> t.Callable[[], float]:
    """Return a callable that returns a float in [0, 1). Prefer rng if provided, else seeded Random, else system random."""
    if rng is not None:
        return rng
    if random_seed is not None:
        _rng = Random(random_seed)
        return _rng.random
    return random


def clamp_sampling_rate(rate: float) -> float:
    """Clamp sampling rate to [0.0, 1.0]. Raises ValueError if not in range (for strict validation)."""
    r = float(rate)
    if not 0.0 <= r <= 1.0:
        raise ValueError(f"sampling_rate must be in [0.0, 1.0], got {rate}")
    return r
