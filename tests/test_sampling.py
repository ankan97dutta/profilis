"""Unit tests for sampling policy: RNG, excludes, overrides, always 5xx."""

from random import Random

import pytest

from profilis.sampling import (
    _compile_excludes,
    _compile_overrides,
    clamp_sampling_rate,
    get_effective_rate,
    make_rng,
    should_exclude_route,
    should_record_request,
    should_sample_request,
)

# --- Deterministic RNG ---


def test_make_rng_with_seed_is_deterministic() -> None:
    rng1 = make_rng(random_seed=42)
    rng2 = make_rng(random_seed=42)
    n = 20
    out1 = [rng1() for _ in range(n)]
    out2 = [rng2() for _ in range(n)]
    assert out1 == out2


def test_make_rng_seed_matches_stdlib_random() -> None:
    """Seeded RNG must match Python's Random(seed).random() sequence."""
    seed = 12345
    rng = make_rng(random_seed=seed)
    stdlib = Random(seed)
    expected = [stdlib.random() for _ in range(10)]
    actual = [rng() for _ in range(10)]
    assert actual == expected


def test_make_rng_callable_overrides_seed() -> None:
    """When rng callable is provided, it is used instead of seed."""
    deterministic = iter([0.0, 0.4, 0.6, 1.0]).__next__
    rng = make_rng(random_seed=999, rng=deterministic)
    assert rng() == 0.0
    assert rng() == 0.4  # noqa: PLR2004
    assert rng() == 0.6  # noqa: PLR2004
    assert rng() == 1.0


def test_make_rng_default_returns_float_in_unit_interval() -> None:
    """Default RNG (no seed/callable) returns values in [0, 1)."""
    rng = make_rng()
    for _ in range(50):
        x = rng()
        assert 0.0 <= x < 1.0


# --- clamp_sampling_rate ---


def test_clamp_sampling_rate_valid() -> None:
    assert clamp_sampling_rate(0.0) == 0.0
    assert clamp_sampling_rate(0.5) == 0.5  # noqa: PLR2004
    assert clamp_sampling_rate(1.0) == 1.0


def test_clamp_sampling_rate_invalid_raises() -> None:
    with pytest.raises(ValueError, match="sampling_rate must be in"):
        clamp_sampling_rate(-0.1)
    with pytest.raises(ValueError, match="sampling_rate must be in"):
        clamp_sampling_rate(1.5)


# --- Route excludes (prefix + regex) ---


def test_should_exclude_route_prefix() -> None:
    compiled = _compile_excludes(["/health", "/static"])
    assert should_exclude_route("/health", compiled) is True
    assert should_exclude_route("/healthz", compiled) is True
    assert should_exclude_route("/static/img/x.png", compiled) is True
    assert should_exclude_route("/api/foo", compiled) is False


def test_should_exclude_route_regex() -> None:
    compiled = _compile_excludes(["re:^/v[12]/"])
    assert should_exclude_route("/v1/foo", compiled) is True
    assert should_exclude_route("/v2/bar", compiled) is True
    assert should_exclude_route("/v3/bar", compiled) is False
    assert should_exclude_route("/api/v1/x", compiled) is False


def test_should_exclude_route_mixed_prefix_and_regex() -> None:
    compiled = _compile_excludes(["/health", "re:^/internal/"])
    assert should_exclude_route("/health", compiled) is True
    assert should_exclude_route("/internal/debug", compiled) is True
    assert should_exclude_route("/api/health", compiled) is False


def test_should_exclude_route_empty_compiled() -> None:
    assert should_exclude_route("/any", []) is False


# --- Per-route overrides ---


def test_get_effective_rate_no_overrides() -> None:
    assert get_effective_rate("/api/foo", [], 0.1) == 0.1  # noqa: PLR2004
    assert get_effective_rate("/", [], 1.0) == 1.0


def test_get_effective_rate_prefix_override() -> None:
    compiled = _compile_overrides([("/api/critical", 1.0), ("/api/", 0.2)])
    assert get_effective_rate("/api/critical", compiled, 0.05) == 1.0
    assert get_effective_rate("/api/items", compiled, 0.05) == 0.2  # noqa: PLR2004
    assert get_effective_rate("/other", compiled, 0.05) == 0.05  # noqa: PLR2004


def test_get_effective_rate_regex_override() -> None:
    compiled = _compile_overrides([("re:^/v[12]/", 1.0)])
    assert get_effective_rate("/v1/foo", compiled, 0.1) == 1.0
    assert get_effective_rate("/v2/bar", compiled, 0.1) == 1.0
    assert get_effective_rate("/v3/bar", compiled, 0.1) == 0.1  # noqa: PLR2004


# --- should_sample_request ---


def test_should_sample_request_rate_one_always_true() -> None:
    def never_used() -> float:
        raise AssertionError("should not be called")

    assert should_sample_request(1.0, never_used) is True


def test_should_sample_request_rate_zero_always_false() -> None:
    def never_used() -> float:
        raise AssertionError("should not be called")

    assert should_sample_request(0.0, never_used) is False


def test_should_sample_request_fractional_uses_rng() -> None:
    # rng <= rate -> sample
    assert should_sample_request(0.5, lambda: 0.0) is True
    assert should_sample_request(0.5, lambda: 0.5) is True
    assert should_sample_request(0.5, lambda: 0.49) is True
    # rng > rate -> no sample
    assert should_sample_request(0.5, lambda: 0.51) is False
    assert should_sample_request(0.5, lambda: 1.0) is False


# --- should_record_request (5xx always when always_sample_errors) ---


def test_should_record_request_sampled_always_recorded() -> None:
    assert should_record_request(True, 200, None, False) is True
    assert should_record_request(True, 500, None, False) is True


def test_should_record_request_5xx_always_when_always_sample_errors() -> None:
    assert should_record_request(False, 500, None, True) is True
    assert should_record_request(False, 503, None, True) is True
    assert should_record_request(False, 599, None, True) is True


def test_should_record_request_exception_always_when_always_sample_errors() -> None:
    assert should_record_request(False, 200, {"type": "ValueError"}, True) is True
    assert should_record_request(False, None, {"type": "RuntimeError"}, True) is True


def test_should_record_request_2xx_not_sampled_not_recorded() -> None:
    assert should_record_request(False, 200, None, True) is False
    assert should_record_request(False, 201, None, True) is False


def test_should_record_request_4xx_not_always_sampled_unless_sampled() -> None:
    # 4xx is not >= 500, so only recorded if sampled
    assert should_record_request(True, 404, None, True) is True
    assert should_record_request(False, 404, None, True) is False
