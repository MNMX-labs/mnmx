"""
Tests for the MNMX PoolAnalyzer.
"""

from __future__ import annotations

import pytest

from mnmx.pool_analyzer import (
    ArbitrageRoute,
    LiquidityDepth,
    PoolAnalyzer,
    PoolAnalysis,
    SwapEstimate,
)
from mnmx.types import PoolState


POOL_A_ADDR = "A" * 44
POOL_B_ADDR = "B" * 44
TOKEN_SOL = "SoLMint111111111111111111111111111111111111"
TOKEN_USDC = "USDCMint11111111111111111111111111111111111"
TOKEN_USDT = "USDTMint11111111111111111111111111111111111"


def _pool(
    addr: str,
    ta: str,
    tb: str,
    ra: int,
    rb: int,
    fee: int = 30,
) -> PoolState:
    return PoolState(
        address=addr,
        token_a_mint=ta,
        token_b_mint=tb,
        reserve_a=ra,
        reserve_b=rb,
        fee_bps=fee,
    )


class TestTvlCalculation:
    def test_tvl_with_both_prices(self) -> None:
        pool = _pool(POOL_A_ADDR, TOKEN_SOL, TOKEN_USDC, 1_000, 100_000)
        analyzer = PoolAnalyzer()
        tvl = analyzer.calculate_tvl(pool, {TOKEN_SOL: 100.0, TOKEN_USDC: 1.0})
        assert tvl == 1_000 * 100.0 + 100_000 * 1.0  # 200_000

    def test_tvl_with_one_price_inferred(self) -> None:
        pool = _pool(POOL_A_ADDR, TOKEN_SOL, TOKEN_USDC, 1_000, 100_000)
        analyzer = PoolAnalyzer()
        tvl = analyzer.calculate_tvl(pool, {TOKEN_SOL: 100.0})
        # reserve_a * price_a = 100_000 for one side
        # inferred price_b = (1000 * 100) / 100_000 = 1.0
        # tvl = 100_000 + 100_000 = 200_000
        assert tvl == 200_000.0

    def test_tvl_with_no_prices(self) -> None:
        pool = _pool(POOL_A_ADDR, TOKEN_SOL, TOKEN_USDC, 1_000, 100_000)
        analyzer = PoolAnalyzer()
        tvl = analyzer.calculate_tvl(pool, {})
        assert tvl == 101_000.0  # fallback: raw sum

    def test_tvl_zero_reserves(self) -> None:
        pool = _pool(POOL_A_ADDR, TOKEN_SOL, TOKEN_USDC, 0, 0)
        analyzer = PoolAnalyzer()
        tvl = analyzer.calculate_tvl(pool, {TOKEN_SOL: 100.0})
        assert tvl == 0.0


class TestDepthAtVariousImpacts:
    def test_higher_impact_allows_more_trade(self) -> None:
        pool = _pool(POOL_A_ADDR, TOKEN_SOL, TOKEN_USDC, 1_000_000, 500_000)
        analyzer = PoolAnalyzer()

        depth_10 = analyzer.calculate_depth(pool, 10)
        depth_100 = analyzer.calculate_depth(pool, 100)
        depth_500 = analyzer.calculate_depth(pool, 500)

        assert depth_100.max_buy_amount >= depth_10.max_buy_amount
        assert depth_500.max_buy_amount >= depth_100.max_buy_amount

    def test_zero_impact_gives_zero_depth(self) -> None:
        pool = _pool(POOL_A_ADDR, TOKEN_SOL, TOKEN_USDC, 1_000_000, 500_000)
        analyzer = PoolAnalyzer()
        depth = analyzer.calculate_depth(pool, 0)
        assert depth.max_buy_amount == 0

    def test_depth_with_prices(self) -> None:
        pool = _pool(POOL_A_ADDR, TOKEN_SOL, TOKEN_USDC, 1_000_000, 500_000)
        analyzer = PoolAnalyzer()
        depth = analyzer.calculate_depth(pool, 100, {TOKEN_SOL: 100.0, TOKEN_USDC: 1.0})
        assert depth.buy_depth_usd > 0


class TestSwapEstimate:
    def test_basic_estimate(self) -> None:
        pool = _pool(POOL_A_ADDR, TOKEN_SOL, TOKEN_USDC, 1_000_000, 500_000)
        analyzer = PoolAnalyzer()
        est = analyzer.estimate_swap_output(pool, 10_000, TOKEN_SOL)
