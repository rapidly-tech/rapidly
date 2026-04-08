"""Tests for math and rounding helpers."""

from rapidly.core.math import rapidly_round


def test_rapidly_round() -> None:
    assert rapidly_round(0) == 0
    assert rapidly_round(0.1) == 0.0
    assert rapidly_round(0.3) == 0.0
    assert rapidly_round(0.5) == 1.0
    assert rapidly_round(0.6) == 1.0
    assert rapidly_round(0.8) == 1.0
    assert rapidly_round(1.0) == 1.0
    assert rapidly_round(1.2) == 1.0
    assert rapidly_round(1.5) == 2.0
    assert rapidly_round(1.7) == 2.0
    assert rapidly_round(101.2) == 101.0
    assert rapidly_round(232.49) == 232.0
    assert rapidly_round(232.5) == 233.0
    assert rapidly_round(232.51) == 233.0
    assert rapidly_round(111111111.0) == 111111111.0

    assert rapidly_round(-0) == -0
    assert rapidly_round(-0.1) == 0.0
    assert rapidly_round(-0.3) == 0.0
    assert rapidly_round(-0.5) == -1.0
    assert rapidly_round(-0.6) == -1.0
    assert rapidly_round(-0.8) == -1.0
    assert rapidly_round(-1.0) == -1.0
    assert rapidly_round(-1.2) == -1.0
    assert rapidly_round(-1.5) == -2.0
    assert rapidly_round(-1.7) == -2.0
    assert rapidly_round(-111) == -111
    assert rapidly_round(-111.0) == -111.0
    assert rapidly_round(-232.2) == -232.0
    assert rapidly_round(-232.49) == -232.0
    assert rapidly_round(-232.5) == -233.0
    assert rapidly_round(-232.51) == -233.0
    assert rapidly_round(-111111111.0) == -111111111.0
