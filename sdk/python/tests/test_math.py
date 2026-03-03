"""
Tests for MNMX math utilities.
"""

from __future__ import annotations

import math

import pytest

from mnmx.math_utils import (
    bps_to_decimal,
    calculate_price_impact,
    calculate_slippage,
    clamp,
    concentrated_liquidity_swap,
    constant_product_input,
    constant_product_output,
    ewma,
    geometric_mean,
    isqrt,
    logistic,
    optimal_split,
    sqrt_price_to_price,
    weighted_average,
)
from mnmx.types import PoolState


POOL_ADDR = "A" * 44
TOKEN_A = "SoLMint111111111111111111111111111111111111"
TOKEN_B = "USDCMint11111111111111111111111111111111111"


def _pool(ra: int, rb: int, fee: int = 30) -> PoolState:
    return PoolState(
        address=POOL_ADDR,
        token_a_mint=TOKEN_A,
        token_b_mint=TOKEN_B,
        reserve_a=ra,
        reserve_b=rb,
        fee_bps=fee,
    )


class TestConstantProductOutput:
    def test_basic_output(self) -> None:
        out = constant_product_output(10_000, 1_000_000, 500_000, 30)
        assert out > 0
        assert out < 10_000  # can't get more than input at 2:1 ratio

    def test_zero_amount(self) -> None:
        assert constant_product_output(0, 1_000_000, 500_000, 30) == 0

    def test_zero_reserves(self) -> None:
        assert constant_product_output(10_000, 0, 500_000, 30) == 0
        assert constant_product_output(10_000, 1_000_000, 0, 30) == 0

    def test_no_fee(self) -> None:
        with_fee = constant_product_output(10_000, 1_000_000, 500_000, 30)
        no_fee = constant_product_output(10_000, 1_000_000, 500_000, 0)
        assert no_fee > with_fee

    def test_higher_fee_less_output(self) -> None:
        low = constant_product_output(10_000, 1_000_000, 500_000, 10)
        high = constant_product_output(10_000, 1_000_000, 500_000, 100)
        assert low > high

    def test_preserves_k_invariant(self) -> None:
        ra, rb = 1_000_000, 500_000
        amount = 10_000
        out = constant_product_output(amount, ra, rb, 0)
        # after swap: new_ra * new_rb >= old k (fees go to LPs)
        new_k = (ra + amount) * (rb - out)
        assert new_k >= ra * rb


class TestConstantProductInputInverse:
    def test_inverse_relationship(self) -> None:
        ra, rb, fee = 1_000_000, 500_000, 30
        # get output for 10_000 input
        out = constant_product_output(10_000, ra, rb, fee)
        # calculate input needed for that output
        inp = constant_product_input(out, ra, rb, fee)
        # should be close to 10_000 (ceiling division adds 1)
        assert abs(inp - 10_000) <= 2

    def test_zero_amount(self) -> None:
        assert constant_product_input(0, 1_000_000, 500_000, 30) == 0

    def test_amount_exceeding_reserves(self) -> None:
        assert constant_product_input(600_000, 1_000_000, 500_000, 30) == 0

    def test_input_always_positive(self) -> None:
        inp = constant_product_input(1_000, 1_000_000, 500_000, 30)
        assert inp > 0


class TestPriceImpact:
    def test_zero_amount_zero_impact(self) -> None:
        assert calculate_price_impact(0, 1_000_000, 500_000) == 0.0

    def test_small_trade_small_impact(self) -> None:
        impact = calculate_price_impact(100, 1_000_000, 500_000)
        assert impact < 0.001

    def test_large_trade_large_impact(self) -> None:
        impact = calculate_price_impact(500_000, 1_000_000, 500_000)
        assert impact > 0.1

    def test_impact_bounded_zero_to_one(self) -> None:
        for amount in [1, 100, 10_000, 500_000, 999_999]:
            impact = calculate_price_impact(amount, 1_000_000, 500_000)
            assert 0.0 <= impact <= 1.0
