"""
Pool analysis utilities for AMM liquidity pools.

Provides TVL calculation, depth analysis, swap estimation, and
multi-pool arbitrage detection.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from mnmx.client import MnmxClient
from mnmx.math_utils import (
    constant_product_output,
    constant_product_input,
    calculate_price_impact,
    bps_to_decimal,
)
from mnmx.types import PoolState


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class SwapEstimate:
    """Estimated output and costs for a potential swap."""
    amount_out: int = 0
    price_impact_bps: int = 0
    effective_price: float = 0.0
    fee_amount: int = 0
    minimum_received: int = 0  # after max slippage


@dataclass
class LiquidityDepth:
    """How much can be traded at various impact levels."""
    impact_bps: int = 0
    max_buy_amount: int = 0
    max_sell_amount: int = 0
    buy_depth_usd: float = 0.0
    sell_depth_usd: float = 0.0


@dataclass
class ArbitrageRoute:
    """A circular route through pools that may yield profit."""
    pools: list[PoolState] = field(default_factory=list)
    tokens: list[str] = field(default_factory=list)
    expected_profit_bps: int = 0
    optimal_amount: int = 0
    estimated_profit: int = 0


@dataclass
class PoolAnalysis:
    """Complete analysis of a single liquidity pool."""
    pool: PoolState
    tvl_usd: float = 0.0
    price_a_in_b: float = 0.0
    price_b_in_a: float = 0.0
    depth_levels: list[LiquidityDepth] = field(default_factory=list)
    fee_apr_estimate: float = 0.0
    volume_24h_estimate: float = 0.0
    imbalance_ratio: float = 0.0


# ---------------------------------------------------------------------------
# PoolAnalyzer
# ---------------------------------------------------------------------------

class PoolAnalyzer:
    """
    Analyzes AMM pools for liquidity depth, arbitrage opportunities,
    and swap estimation.
    """

    def __init__(self, client: MnmxClient | None = None) -> None:
        self.client = client

    async def analyze_pool(self, pool_address: str) -> PoolAnalysis:
        """
        Fetch a pool's state from the engine and run a full analysis.

        Requires a connected MnmxClient.
        """
        if self.client is None:
            raise RuntimeError("PoolAnalyzer requires an MnmxClient for remote analysis")

        pool = await self.client.get_pool_state(pool_address)
        prices: dict[str, float] = {}
        # best-effort price fetch
        try:
            balances_a = await self.client.get_token_balances(pool.token_a_mint)
            balances_b = await self.client.get_token_balances(pool.token_b_mint)
        except Exception:
            pass

        return self.analyze_pool_local(pool, prices)

    def analyze_pool_local(
        self,
        pool: PoolState,
        prices: dict[str, float] | None = None,
    ) -> PoolAnalysis:
        """Run analysis on a local PoolState without an API call."""
        prices = prices or {}
        tvl = self.calculate_tvl(pool, prices)

        depth_levels = [
            self.calculate_depth(pool, bps, prices)
            for bps in [10, 50, 100, 200, 500]
        ]

        price_a_in_b = pool.reserve_b / pool.reserve_a if pool.reserve_a > 0 else 0.0
        price_b_in_a = pool.reserve_a / pool.reserve_b if pool.reserve_b > 0 else 0.0

        total_reserves = pool.reserve_a + pool.reserve_b
        if total_reserves > 0:
            imbalance = abs(pool.reserve_a - pool.reserve_b) / total_reserves
        else:
            imbalance = 0.0

        # rough APR estimate: assume daily volume is 5% of TVL, fees on that
        daily_volume = tvl * 0.05
        daily_fees = daily_volume * bps_to_decimal(pool.fee_bps)
        fee_apr = (daily_fees * 365) / tvl if tvl > 0 else 0.0

        return PoolAnalysis(
            pool=pool,
            tvl_usd=tvl,
            price_a_in_b=price_a_in_b,
            price_b_in_a=price_b_in_a,
            depth_levels=depth_levels,
            fee_apr_estimate=fee_apr,
            volume_24h_estimate=daily_volume,
            imbalance_ratio=imbalance,
        )

    def calculate_tvl(
        self, pool: PoolState, prices: dict[str, float]
    ) -> float:
        """
        Calculate total value locked in USD.

        If token prices are unavailable, falls back to reserve ratio heuristics.
        """
        price_a = prices.get(pool.token_a_mint, 0.0)
        price_b = prices.get(pool.token_b_mint, 0.0)

        if price_a > 0 and price_b > 0:
            return pool.reserve_a * price_a + pool.reserve_b * price_b

        # if we have one price, infer the other via the pool ratio
        if price_a > 0 and pool.reserve_a > 0:
            inferred_b = (pool.reserve_a * price_a) / pool.reserve_b if pool.reserve_b > 0 else 0.0
            return pool.reserve_a * price_a + pool.reserve_b * inferred_b

        if price_b > 0 and pool.reserve_b > 0:
            inferred_a = (pool.reserve_b * price_b) / pool.reserve_a if pool.reserve_a > 0 else 0.0
            return pool.reserve_a * inferred_a + pool.reserve_b * price_b

        # no prices at all — return raw reserves sum as a proxy
        return float(pool.reserve_a + pool.reserve_b)

    def calculate_depth(
        self,
        pool: PoolState,
        impact_bps: int,
        prices: dict[str, float] | None = None,
    ) -> LiquidityDepth:
        """
        Determine how much can be bought/sold before hitting a given impact.

        Uses binary search to find the maximum trade size that stays within
        the specified price impact.
        """
        prices = prices or {}
        target_impact = impact_bps / 10_000

        max_buy = self._binary_search_depth(
            pool.reserve_a, pool.reserve_b, target_impact
        )
        max_sell = self._binary_search_depth(
            pool.reserve_b, pool.reserve_a, target_impact
        )

        price_a = prices.get(pool.token_a_mint, 1.0)
        price_b = prices.get(pool.token_b_mint, 1.0)

        return LiquidityDepth(
            impact_bps=impact_bps,
            max_buy_amount=max_buy,
            max_sell_amount=max_sell,
            buy_depth_usd=max_buy * price_a,
            sell_depth_usd=max_sell * price_b,
        )

    def estimate_swap_output(
        self,
        pool: PoolState,
        amount_in: int,
        token_in: str,
    ) -> SwapEstimate:
        """Estimate the output of a swap without executing it."""
        if token_in == pool.token_a_mint:
            reserve_in, reserve_out = pool.reserve_a, pool.reserve_b
        else:
            reserve_in, reserve_out = pool.reserve_b, pool.reserve_a

        amount_out = constant_product_output(
            amount_in, reserve_in, reserve_out, pool.fee_bps
        )

        impact = calculate_price_impact(amount_in, reserve_in, reserve_out)
        impact_bps = int(impact * 10_000)

        fee_amount = (amount_in * pool.fee_bps) // 10_000
        effective_price = amount_in / amount_out if amount_out > 0 else 0.0
        min_received = int(amount_out * 0.995)  # 0.5% default slippage

        return SwapEstimate(
            amount_out=amount_out,
            price_impact_bps=impact_bps,
            effective_price=effective_price,
            fee_amount=fee_amount,
            minimum_received=min_received,
        )

    def find_arbitrage(
        self, pools: list[PoolState]
    ) -> list[ArbitrageRoute]:
        """
        Detect circular arbitrage opportunities across a set of pools.

        Searches for two-pool triangular routes where buying on one pool
        and selling on another yields a profit.
        """
        routes: list[ArbitrageRoute] = []

        # build adjacency: token -> list of (pool, other_token)
        adjacency: dict[str, list[tuple[PoolState, str]]] = {}
        for pool in pools:
            adjacency.setdefault(pool.token_a_mint, []).append((pool, pool.token_b_mint))
            adjacency.setdefault(pool.token_b_mint, []).append((pool, pool.token_a_mint))

        visited_pairs: set[tuple[str, str]] = set()

        for token_start, edges in adjacency.items():
            for pool1, token_mid in edges:
                if token_mid not in adjacency:
                    continue
                for pool2, token_end in adjacency[token_mid]:
                    if pool2.address == pool1.address:
                        continue
                    if token_end != token_start:
                        continue

                    pair_key = tuple(sorted([pool1.address, pool2.address]))
                    if pair_key in visited_pairs:
                        continue
                    visited_pairs.add(pair_key)

                    # check if route is profitable
                    test_amount = min(pool1.reserve_a, pool1.reserve_b) // 100
                    if test_amount == 0:
                        continue

                    # leg 1: token_start -> token_mid on pool1
                    out1 = self._swap_through_pool(pool1, test_amount, token_start)
                    if out1 <= 0:
                        continue

                    # leg 2: token_mid -> token_start on pool2
                    out2 = self._swap_through_pool(pool2, out1, token_mid)
                    if out2 <= 0:
                        continue

                    profit = out2 - test_amount
                    if profit > 0:
                        profit_bps = int((profit / test_amount) * 10_000)
                        route = ArbitrageRoute(
                            pools=[pool1, pool2],
                            tokens=[token_start, token_mid, token_start],
                            expected_profit_bps=profit_bps,
                        )
                        route.optimal_amount = self.optimal_arbitrage_amount(route)
                        route.estimated_profit = self.calculate_route_profit(
                            route, route.optimal_amount
                        )
                        if route.estimated_profit > 0:
                            routes.append(route)

        routes.sort(key=lambda r: r.estimated_profit, reverse=True)
        return routes

    def calculate_route_profit(
        self, route: ArbitrageRoute, amount: int
    ) -> int:
        """Calculate the profit of executing an arbitrage route with a given input."""
        if len(route.pools) < 2 or len(route.tokens) < 3:
            return 0

        current_amount = amount
        for i, pool in enumerate(route.pools):
            token_in = route.tokens[i]
            current_amount = self._swap_through_pool(pool, current_amount, token_in)
            if current_amount <= 0:
                return 0

        return current_amount - amount

    def optimal_arbitrage_amount(self, route: ArbitrageRoute) -> int:
        """
        Find the input amount that maximises profit via binary search.

        Searches between 1 and 10% of the smallest pool's reserves.
        """
        if not route.pools:
            return 0

        min_reserve = min(
            min(p.reserve_a, p.reserve_b) for p in route.pools
        )
        upper = min_reserve // 10
        if upper <= 0:
            return 0

        lo, hi = 1, upper
        best_amount = 0
        best_profit = 0

        while lo <= hi:
            mid = (lo + hi) // 2
            profit = self.calculate_route_profit(route, mid)

            if profit > best_profit:
                best_profit = profit
                best_amount = mid

            # check gradient: does increasing amount still help?
            profit_higher = self.calculate_route_profit(route, mid + max(1, mid // 10))
            if profit_higher > profit:
                lo = mid + 1
            else:
                hi = mid - 1

        return best_amount

    # -- internal -----------------------------------------------------------

    @staticmethod
    def _swap_through_pool(
        pool: PoolState, amount_in: int, token_in: str
    ) -> int:
        """Execute a simulated swap through a pool."""
        if token_in == pool.token_a_mint:
            return constant_product_output(
                amount_in, pool.reserve_a, pool.reserve_b, pool.fee_bps
            )
        elif token_in == pool.token_b_mint:
            return constant_product_output(
                amount_in, pool.reserve_b, pool.reserve_a, pool.fee_bps
            )
        return 0

    @staticmethod
    def _binary_search_depth(
        reserve_in: int, reserve_out: int, target_impact: float
    ) -> int:
        """Binary search for the max trade size within a target price impact."""
        if reserve_in <= 0 or reserve_out <= 0:
            return 0

        lo, hi = 0, reserve_in
        result = 0

        for _ in range(64):  # enough iterations for convergence
            if lo > hi:
                break
            mid = (lo + hi) // 2
            impact = calculate_price_impact(mid, reserve_in, reserve_out)
            if impact <= target_impact:
                result = mid
                lo = mid + 1
            else:
                hi = mid - 1

        return result
