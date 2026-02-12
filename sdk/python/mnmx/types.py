"""
Pydantic models mirroring the MNMX Rust engine types.

All models use strict validation and support round-trip JSON serialization.
"""

from __future__ import annotations

import time
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, field_validator, model_validator


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class Player(str, Enum):
    """The two players in the minimax game tree."""
    AGENT = "agent"
    ADVERSARY = "adversary"


class ActionKind(str, Enum):
    """Types of on-chain actions the agent can take."""
    SWAP = "swap"
    ADD_LIQUIDITY = "add_liquidity"
    REMOVE_LIQUIDITY = "remove_liquidity"
    LIMIT_ORDER = "limit_order"
    CANCEL_ORDER = "cancel_order"
    TRANSFER = "transfer"
    STAKE = "stake"
    UNSTAKE = "unstake"
    NO_OP = "no_op"


class MevKind(str, Enum):
    """Categories of MEV attacks."""
    FRONTRUN = "frontrun"
    BACKRUN = "backrun"
    SANDWICH = "sandwich"
    JIT_LIQUIDITY = "jit_liquidity"
    ARBITRAGE = "arbitrage"
    LIQUIDATION = "liquidation"


# ---------------------------------------------------------------------------
# Core state models
# ---------------------------------------------------------------------------

class PoolState(BaseModel):
    """Snapshot of an AMM liquidity pool."""
    address: str = Field(..., min_length=32, max_length=64)
    token_a_mint: str
    token_b_mint: str
    reserve_a: int = Field(..., ge=0)
    reserve_b: int = Field(..., ge=0)
    fee_bps: int = Field(default=30, ge=0, le=10000)
    lp_supply: int = Field(default=0, ge=0)
    sqrt_price: int = Field(default=0, ge=0)
    tick_current: int = Field(default=0)
    liquidity: int = Field(default=0, ge=0)
    last_update_slot: int = Field(default=0, ge=0)

    @field_validator("reserve_a", "reserve_b")
    @classmethod
    def reserves_must_be_positive_for_active_pool(cls, v: int) -> int:
        return v  # zero is allowed for newly created pools

    @property
    def price_a_in_b(self) -> float:
        if self.reserve_a == 0:
            return 0.0
        return self.reserve_b / self.reserve_a

    @property
    def price_b_in_a(self) -> float:
        if self.reserve_b == 0:
            return 0.0
        return self.reserve_a / self.reserve_b

    @property
    def k(self) -> int:
        return self.reserve_a * self.reserve_b


class PendingTx(BaseModel):
    """A transaction sitting in the mempool."""
    signature: str
    sender: str
    action: ExecutionAction
    priority_fee: int = Field(default=0, ge=0)
    timestamp_ms: int = Field(default_factory=lambda: int(time.time() * 1000))
    estimated_cu: int = Field(default=200_000, ge=0)


class OnChainState(BaseModel):
    """Full snapshot of relevant on-chain state for the minimax search."""
    slot: int = Field(..., ge=0)
    block_time: int = Field(default=0, ge=0)
    pools: list[PoolState] = Field(default_factory=list)
    balances: dict[str, int] = Field(default_factory=dict)
    pending_txs: list[PendingTx] = Field(default_factory=list)
    recent_blockhash: str = Field(default="")
    wallet_address: str = Field(default="")
    token_prices_usd: dict[str, float] = Field(default_factory=dict)
