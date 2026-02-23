"""
Command-line interface for the MNMX SDK.

Provides subcommands for search, simulation, backtesting, pool analysis,
and threat detection with optional JSON output.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path
from typing import Any

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text

from mnmx.types import (
    ActionKind,
    BacktestConfig,
    ExecutionAction,
    OnChainState,
    SearchConfig,
    SimulationConfig,
)


console = Console()


def main() -> None:
    """Entry point for the mnmx CLI."""
    parser = argparse.ArgumentParser(
        prog="mnmx",
        description="MNMX SDK — Minimax execution engine CLI",
    )
    parser.add_argument(
        "--json", action="store_true", help="Output results as JSON"
    )
    parser.add_argument(
        "--endpoint",
        default="http://localhost:8080",
        help="MNMX engine endpoint URL",
    )
    parser.add_argument("--api-key", default=None, help="API key for authentication")

    subparsers = parser.add_subparsers(dest="command", required=True)

    # -- search -------------------------------------------------------------
    p_search = subparsers.add_parser("search", help="Run minimax search")
    p_search.add_argument("--wallet", required=True, help="Wallet address")
    p_search.add_argument(
        "--action",
        required=True,
        choices=["swap", "add_liquidity", "remove_liquidity"],
    )
    p_search.add_argument("--amount", required=True, type=int, help="Amount in lamports")
    p_search.add_argument("--pool", required=True, help="Pool address")
    p_search.add_argument("--token-in", default="SOL", help="Input token mint")
    p_search.add_argument("--token-out", default="USDC", help="Output token mint")
    p_search.add_argument("--depth", type=int, default=6, help="Search depth")

    # -- simulate -----------------------------------------------------------
    p_sim = subparsers.add_parser("simulate", help="Simulate an action locally")
    p_sim.add_argument("--state", required=True, help="Path to state JSON file")
    p_sim.add_argument("--action", required=True, help="Path to action JSON file")

    # -- backtest -----------------------------------------------------------
    p_bt = subparsers.add_parser("backtest", help="Run a backtest")
    p_bt.add_argument("--data", required=True, help="Path to historical states JSON")
    p_bt.add_argument(
        "--strategy",
        default="simple",
        choices=["simple", "mev-aware"],
        help="Strategy to backtest",
    )
    p_bt.add_argument("--amount", type=int, default=1_000_000, help="Trade amount")
    p_bt.add_argument("--token-in", default="SOL")
    p_bt.add_argument("--token-out", default="USDC")

    # -- analyze-pool -------------------------------------------------------
    p_pool = subparsers.add_parser("analyze-pool", help="Analyze a liquidity pool")
    p_pool.add_argument("--pool", required=True, help="Pool address")
    p_pool.add_argument("--state", default=None, help="Path to state JSON (for local analysis)")

    # -- threats ------------------------------------------------------------
    p_threat = subparsers.add_parser("threats", help="Detect MEV threats")
    p_threat.add_argument("--action", required=True, help="Path to action JSON file")
    p_threat.add_argument("--state", required=True, help="Path to state JSON file")

    args = parser.parse_args()

    try:
        if args.command == "search":
            asyncio.run(_cmd_search(args))
        elif args.command == "simulate":
            _cmd_simulate(args)
        elif args.command == "backtest":
            _cmd_backtest(args)
        elif args.command == "analyze-pool":
            _cmd_analyze_pool(args)
        elif args.command == "threats":
            asyncio.run(_cmd_threats(args))
    except FileNotFoundError as exc:
        console.print(f"[red]File not found:[/red] {exc}")
        sys.exit(1)
    except KeyboardInterrupt:
        console.print("\n[yellow]Interrupted[/yellow]")
        sys.exit(130)
    except Exception as exc:
        console.print(f"[red]Error:[/red] {exc}")
        sys.exit(1)


# ---------------------------------------------------------------------------
# Subcommand implementations
# ---------------------------------------------------------------------------

async def _cmd_search(args: argparse.Namespace) -> None:
    from mnmx.client import MnmxClient

    action = ExecutionAction(
        kind=ActionKind(args.action),
        pool_address=args.pool,
        token_in=args.token_in,
        token_out=args.token_out,
        amount_in=args.amount,
    )
    state = OnChainState(
        slot=0,
        wallet_address=args.wallet,
    )
    config = SearchConfig(max_depth=args.depth)

    async with MnmxClient(args.endpoint, api_key=args.api_key) as client:
        plan = await client.search(state, [action], config)

    if args.json:
        print(plan.model_dump_json(indent=2))
        return

    table = Table(title="Search Results")
    table.add_column("Metric", style="cyan")
    table.add_column("Value", style="green")
    table.add_row("Expected value", f"{plan.expected_value:.6f}")
    table.add_row("Worst-case value", f"{plan.worst_case_value:.6f}")
    table.add_row("Search depth", str(plan.search_depth))
    table.add_row("Nodes explored", f"{plan.nodes_explored:,}")
    table.add_row("Time (ms)", f"{plan.time_ms:.1f}")
    table.add_row("Actions", str(len(plan.actions)))
    table.add_row("Threats mitigated", str(len(plan.threats_mitigated)))
    console.print(table)


def _cmd_simulate(args: argparse.Namespace) -> None:
    from mnmx.simulator import Simulator

    state_data = json.loads(Path(args.state).read_text())
    action_data = json.loads(Path(args.action).read_text())

    state = OnChainState.model_validate(state_data)
    action = ExecutionAction.model_validate(action_data)
