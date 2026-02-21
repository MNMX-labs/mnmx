"""
Backtesting framework for MNMX trading strategies.

Replays historical on-chain states through a strategy, recording trades,
computing PnL, and producing risk-adjusted performance metrics.
"""

from __future__ import annotations

import math
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from mnmx.math_utils import constant_product_output, calculate_slippage
from mnmx.simulator import Simulator
from mnmx.types import (
    ActionKind,
    BacktestConfig,
    BacktestResult,
    ExecutionAction,
    MevKind,
    MevThreat,
    OnChainState,
    SimulationConfig,
    SimulationResult,
    TradeRecord,
)


# ---------------------------------------------------------------------------
# Strategy protocol
# ---------------------------------------------------------------------------

class Strategy(ABC):
    """Abstract base class for backtestable trading strategies."""

    @abstractmethod
    def decide(self, state: OnChainState) -> ExecutionAction | None:
        """
        Examine current on-chain state and decide on an action.

        Return None to skip this slot (no trade).
        """
        ...

    def on_trade_result(self, record: TradeRecord) -> None:
        """Optional callback after each trade is recorded."""


# ---------------------------------------------------------------------------
# Built-in strategies
# ---------------------------------------------------------------------------

class SimpleSwapStrategy(Strategy):
    """
    Naive strategy: swap a fixed amount on the first available pool
    whenever the price impact is below a threshold.
    """

    def __init__(
        self,
        token_in: str,
        token_out: str,
        amount: int,
        max_impact_bps: int = 100,
    ) -> None:
        self.token_in = token_in
        self.token_out = token_out
        self.amount = amount
        self.max_impact_bps = max_impact_bps

    def decide(self, state: OnChainState) -> ExecutionAction | None:
        balance = state.balances.get(self.token_in, 0)
        if balance < self.amount:
            return None

        for pool in state.pools:
            tokens = {pool.token_a_mint, pool.token_b_mint}
            if self.token_in in tokens and self.token_out in tokens:
                if pool.token_a_mint == self.token_in:
                    reserve_in, reserve_out = pool.reserve_a, pool.reserve_b
                else:
                    reserve_in, reserve_out = pool.reserve_b, pool.reserve_a

                if reserve_in == 0 or reserve_out == 0:
                    continue

                from mnmx.math_utils import calculate_price_impact
                impact = calculate_price_impact(self.amount, reserve_in, reserve_out)
                if impact * 10_000 > self.max_impact_bps:
                    continue

                min_out = constant_product_output(
                    self.amount, reserve_in, reserve_out, pool.fee_bps
                )
                # allow 1% slippage from simulated output
                min_out = int(min_out * 0.99)

                return ExecutionAction(
                    kind=ActionKind.SWAP,
                    pool_address=pool.address,
                    token_in=self.token_in,
                    token_out=self.token_out,
                    amount_in=self.amount,
                    min_amount_out=min_out,
                )
        return None


class MevAwareStrategy(Strategy):
    """
    Strategy that avoids trading when MEV risk is elevated.

    Monitors pending transactions and skips trades when sandwich or
    frontrun threats are detected in the mempool.
    """

    def __init__(
        self,
        token_in: str,
        token_out: str,
        amount: int,
        max_impact_bps: int = 100,
        max_mev_risk: float = 0.3,
    ) -> None:
        self.token_in = token_in
        self.token_out = token_out
        self.amount = amount
        self.max_impact_bps = max_impact_bps
        self.max_mev_risk = max_mev_risk
        self._consecutive_skips = 0
        self._max_consecutive_skips = 5

    def decide(self, state: OnChainState) -> ExecutionAction | None:
        balance = state.balances.get(self.token_in, 0)
        if balance < self.amount:
            return None

        for pool in state.pools:
            tokens = {pool.token_a_mint, pool.token_b_mint}
            if self.token_in not in tokens or self.token_out not in tokens:
                continue

            if pool.token_a_mint == self.token_in:
                reserve_in, reserve_out = pool.reserve_a, pool.reserve_b
            else:
                reserve_in, reserve_out = pool.reserve_b, pool.reserve_a

            if reserve_in == 0 or reserve_out == 0:
                continue

            # check MEV risk from pending txs
            competing = sum(
                1 for tx in state.pending_txs
                if tx.action.pool_address == pool.address
            )
            size_ratio = self.amount / reserve_in if reserve_in > 0 else 1.0
            mev_risk = min(1.0, size_ratio * 5.0 + competing * 0.1)

            # allow override after too many skips
            if mev_risk > self.max_mev_risk and self._consecutive_skips < self._max_consecutive_skips:
                self._consecutive_skips += 1
                continue

            from mnmx.math_utils import calculate_price_impact
            impact = calculate_price_impact(self.amount, reserve_in, reserve_out)
            if impact * 10_000 > self.max_impact_bps:
                continue

            min_out = constant_product_output(
                self.amount, reserve_in, reserve_out, pool.fee_bps
            )
            min_out = int(min_out * 0.99)

            self._consecutive_skips = 0
            return ExecutionAction(
                kind=ActionKind.SWAP,
                pool_address=pool.address,
                token_in=self.token_in,
                token_out=self.token_out,
                amount_in=self.amount,
                min_amount_out=min_out,
                priority_fee_lamports=10_000 if mev_risk > 0.2 else 5000,
            )

        return None


# ---------------------------------------------------------------------------
# Backtest metrics
# ---------------------------------------------------------------------------

@dataclass
class BacktestMetrics:
    """Summary performance metrics from a backtest."""
    total_pnl: int = 0
    win_rate: float = 0.0
    sharpe_ratio: float = 0.0
    max_drawdown: float = 0.0
    avg_slippage_bps: float = 0.0
    mev_losses: int = 0
    total_gas: int = 0
    num_trades: int = 0
    profit_factor: float = 0.0
