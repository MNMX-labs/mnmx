"""Core data types for the MNMX SDK."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Literal


class Chain(str, Enum):
    """Supported blockchain networks."""

    ETHEREUM = "ethereum"
    POLYGON = "polygon"
    ARBITRUM = "arbitrum"
    OPTIMISM = "optimism"
    AVALANCHE = "avalanche"
    BSC = "bsc"
    BASE = "base"
    SOLANA = "solana"
    FANTOM = "fantom"
    CELO = "celo"

    @classmethod
    def from_str(cls, value: str) -> "Chain":
        """Resolve a chain from a case-insensitive string."""
        normalized = value.strip().lower()
        for member in cls:
            if member.value == normalized:
                return member
        raise ValueError(f"Unknown chain: {value!r}. Supported: {[c.value for c in cls]}")

    @classmethod
    def all_names(cls) -> list[str]:
        return [c.value for c in cls]


Strategy = Literal["minimax", "maximin", "balanced", "aggressive", "conservative"]

VALID_STRATEGIES: list[Strategy] = ["minimax", "maximin", "balanced", "aggressive", "conservative"]


@dataclass(frozen=True)
class Token:
    """A token on a specific chain."""

    symbol: str
    chain: Chain
    decimals: int = 18
    address: str = ""

    def __post_init__(self) -> None:
        if self.decimals < 0 or self.decimals > 36:
            raise ValueError(f"decimals must be in [0, 36], got {self.decimals}")

    @property
    def display_name(self) -> str:
        return f"{self.symbol} ({self.chain.value})"

    def __str__(self) -> str:
        return self.display_name


@dataclass
class RouteHop:
    """A single hop in a cross-chain route."""

    from_chain: Chain
    to_chain: Chain
    from_token: str
    to_token: str
    bridge: str
    input_amount: float
    output_amount: float
    fee: float
    estimated_time: int  # seconds

    @property
    def fee_percentage(self) -> float:
        if self.input_amount == 0:
            return 0.0
        return (self.fee / self.input_amount) * 100.0

    @property
    def is_cross_chain(self) -> bool:
        return self.from_chain != self.to_chain

    def __post_init__(self) -> None:
        if self.input_amount < 0:
            raise ValueError("input_amount must be non-negative")
        if self.output_amount < 0:
            raise ValueError("output_amount must be non-negative")
        if self.fee < 0:
            raise ValueError("fee must be non-negative")
        if self.estimated_time < 0:
            raise ValueError("estimated_time must be non-negative")


@dataclass
class Route:
    """A complete route from source to destination."""

    path: list[RouteHop]
    expected_output: float
    guaranteed_minimum: float
    total_fees: float
    estimated_time: int  # seconds
    minimax_score: float
    strategy: str

    @property
    def hop_count(self) -> int:
        return len(self.path)

    @property
    def bridges_used(self) -> list[str]:
        return list(dict.fromkeys(hop.bridge for hop in self.path))

    @property
    def chains_visited(self) -> list[Chain]:
        chains: list[Chain] = []
        for hop in self.path:
            if hop.from_chain not in chains:
                chains.append(hop.from_chain)
            if hop.to_chain not in chains:
                chains.append(hop.to_chain)
        return chains

    @property
    def fee_percentage(self) -> float:
        if not self.path:
            return 0.0
        initial = self.path[0].input_amount
        if initial == 0:
            return 0.0
        return (self.total_fees / initial) * 100.0

    def __str__(self) -> str:
        chain_str = " -> ".join(c.value for c in self.chains_visited)
        return (
            f"Route({chain_str}, output={self.expected_output:.4f}, "
            f"min={self.guaranteed_minimum:.4f}, score={self.minimax_score:.4f})"
        )


@dataclass
class RouteRequest:
    """A request to find a route."""

    from_chain: Chain
    from_token: str
    amount: float
    to_chain: Chain
    to_token: str
    strategy: Strategy = "minimax"
    max_hops: int = 3
    slippage_tolerance: float = 0.005  # 0.5%

    def __post_init__(self) -> None:
        if self.amount <= 0:
            raise ValueError("amount must be positive")
        if self.max_hops < 1:
            raise ValueError("max_hops must be >= 1")
        if not 0.0 <= self.slippage_tolerance <= 1.0:
            raise ValueError("slippage_tolerance must be in [0, 1]")
        if self.strategy not in VALID_STRATEGIES:
            raise ValueError(
                f"strategy must be one of {VALID_STRATEGIES}, got {self.strategy!r}"
            )


@dataclass
class BridgeQuote:
    """A quote from a bridge for a specific transfer."""

    bridge: str
    input_amount: float
    output_amount: float
    fee: float
    estimated_time: int  # seconds
    liquidity_depth: float
    expires_at: float = 0.0  # unix timestamp

    def __post_init__(self) -> None:
        if self.expires_at == 0.0:
            self.expires_at = time.time() + 30.0  # 30 second default expiry

    @property
    def is_expired(self) -> bool:
        return time.time() > self.expires_at

    @property
    def slippage(self) -> float:
        if self.input_amount == 0:
            return 0.0
        return 1.0 - (self.output_amount + self.fee) / self.input_amount


@dataclass
class BridgeHealth:
    """Health status of a bridge."""

    online: bool
    congestion: float  # 0.0 (none) to 1.0 (fully congested)
    success_rate: float  # 0.0 to 1.0
    median_confirm_time: int  # seconds

    @property
    def is_healthy(self) -> bool:
        return self.online and self.congestion < 0.8 and self.success_rate > 0.9

    @property
    def reliability_score(self) -> float:
        if not self.online:
            return 0.0
        return self.success_rate * (1.0 - self.congestion)


@dataclass
class ScoringWeights:
    """Weights for each dimension of route scoring.  All values in [0, 1]."""

    fees: float = 0.25
    slippage: float = 0.25
    speed: float = 0.20
    reliability: float = 0.20
    mev_exposure: float = 0.10

    def __post_init__(self) -> None:
        for name in ("fees", "slippage", "speed", "reliability", "mev_exposure"):
            val = getattr(self, name)
            if not 0.0 <= val <= 1.0:
                raise ValueError(f"{name} weight must be in [0, 1], got {val}")

    @property
    def total(self) -> float:
        return self.fees + self.slippage + self.speed + self.reliability + self.mev_exposure

    def normalized(self) -> "ScoringWeights":
        t = self.total
        if t == 0:
            return ScoringWeights(0.2, 0.2, 0.2, 0.2, 0.2)
        return ScoringWeights(
            fees=self.fees / t,
            slippage=self.slippage / t,
            speed=self.speed / t,
            reliability=self.reliability / t,
            mev_exposure=self.mev_exposure / t,
        )

