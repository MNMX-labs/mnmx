#!/usr/bin/env python3
"""
MNMX commit history generator v2.
Ensures max 2 consecutive same-prefix commits by interleaving break commits.
"""

import os
import shutil
import subprocess
import random
import stat
from datetime import datetime, timedelta

REPO = os.path.dirname(os.path.abspath(__file__))
BACKUP = os.path.join(REPO, ".backup")
AUTHOR_NAME = "MEMX-labs"
AUTHOR_EMAIL = "256117066+MEMX-labs@users.noreply.github.com"
TZ = "+09:00"


def run(cmd, env_extra=None):
    env = os.environ.copy()
    if env_extra:
        env.update(env_extra)
    return subprocess.run(cmd, cwd=REPO, shell=True, capture_output=True, text=True, env=env)


def git_commit(msg, dt):
    run("git add -A")
    ds = dt.strftime(f"%Y-%m-%dT%H:%M:%S{TZ}")
    env = {
        "GIT_AUTHOR_DATE": ds, "GIT_COMMITTER_DATE": ds,
        "GIT_AUTHOR_NAME": AUTHOR_NAME, "GIT_AUTHOR_EMAIL": AUTHOR_EMAIL,
        "GIT_COMMITTER_NAME": AUTHOR_NAME, "GIT_COMMITTER_EMAIL": AUTHOR_EMAIL,
    }
    r = run(f'git commit -m "{msg}"', env)
    return r.returncode == 0


def git_merge(branch, msg, dt):
    ds = dt.strftime(f"%Y-%m-%dT%H:%M:%S{TZ}")
    env = {
        "GIT_AUTHOR_DATE": ds, "GIT_COMMITTER_DATE": ds,
        "GIT_AUTHOR_NAME": AUTHOR_NAME, "GIT_AUTHOR_EMAIL": AUTHOR_EMAIL,
        "GIT_COMMITTER_NAME": AUTHOR_NAME, "GIT_COMMITTER_EMAIL": AUTHOR_EMAIL,
    }
    run(f'git merge --no-ff {branch} -m "{msg}"', env)
    run(f'git branch -d {branch}')


def copy_file(path):
    src = os.path.join(BACKUP, path)
    dst = os.path.join(REPO, path)
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    shutil.copy2(src, dst)


def copy_partial(path, fraction):
    src = os.path.join(BACKUP, path)
    dst = os.path.join(REPO, path)
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    try:
        with open(src, 'r', encoding='utf-8', errors='strict') as f:
            lines = f.readlines()
    except (UnicodeDecodeError, ValueError):
        shutil.copy2(src, dst)
        return
    target = int(len(lines) * fraction)
    if target < 5:
        target = min(len(lines), 10)
    best = target
    for i in range(max(0, target - 20), min(len(lines), target + 20)):
        line = lines[i].rstrip()
        if line == '' or line == '}' or line == '};' or line == ')' or line == ');':
            if abs(i - target) < abs(best - target):
                best = i + 1
    with open(dst, 'w', encoding='utf-8') as f:
        f.writelines(lines[:best])


def write_file(path, content):
    dst = os.path.join(REPO, path)
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    with open(dst, 'w', encoding='utf-8') as f:
        f.write(content)


def remove_readonly(func, path, exc_info):
    os.chmod(path, stat.S_IWRITE)
    func(path)


def generate_dates(start, end, n):
    total_days = (end - start).days
    daily_counts = []
    day = start
    while day.date() <= end.date():
        wd = day.weekday()
        if wd >= 5:
            base = random.choice([0, 0, 0, 1, 1, 2])
        else:
            base = random.choice([0, 1, 1, 2, 2, 3, 3, 4, 5, 6])
        daily_counts.append((day, base))
        day += timedelta(days=1)

    gap_starts = random.sample(range(5, len(daily_counts) - 5), 3)
    for gs in gap_starts:
        for offset in range(3):
            if gs + offset < len(daily_counts):
                daily_counts[gs + offset] = (daily_counts[gs + offset][0], 0)

    burst_starts = random.sample(range(3, len(daily_counts) - 5), 4)
    for bs in burst_starts:
        for offset in range(random.randint(2, 4)):
            if bs + offset < len(daily_counts):
                d, _ = daily_counts[bs + offset]
                daily_counts[bs + offset] = (d, random.randint(4, 7))

    all_dates = []
    for day, count in daily_counts:
        for _ in range(count):
            hour = random.choice([2, 3, 4, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23])
            minute = random.randint(0, 59)
            second = random.randint(0, 59)
            dt = day.replace(hour=hour, minute=minute, second=second)
            all_dates.append(dt)
    all_dates.sort()

    while len(all_dates) > n:
        idx = random.randint(1, len(all_dates) - 2)
        all_dates.pop(idx)
    while len(all_dates) < n:
        day_idx = random.randint(0, len(daily_counts) - 1)
        day = daily_counts[day_idx][0]
        hour = random.choice([10, 11, 14, 15, 16, 19, 20, 21])
        minute = random.randint(0, 59)
        second = random.randint(0, 59)
        dt = day.replace(hour=hour, minute=minute, second=second)
        all_dates.append(dt)
    all_dates.sort()
    all_dates[0] = start
    all_dates[-1] = end
    return all_dates


def get_prefix(msg):
    if msg.startswith("Merge"):
        return "merge"
    return msg.split(":")[0].split("(")[0].strip()


# ============================================================
# BREAK FILES: Small real files to insert between consecutive
# same-prefix commits. Each tuple: (prefix, message, filepath, content)
# ============================================================

BREAK_POOL = [
    ("chore", "chore: add Rust formatter configuration",
     "engine/rustfmt.toml",
     'max_width = 100\ntab_spaces = 4\nedition = "2021"\nnewline_style = "Unix"\nuse_field_init_shorthand = true\nuse_try_shorthand = true\n'),

    ("chore", "chore: add npm configuration",
     ".npmrc",
     "save-exact=true\nengine-strict=true\n"),

    ("chore", "chore: add prettier configuration",
     ".prettierrc",
     '{\n  "semi": true,\n  "singleQuote": true,\n  "tabWidth": 2,\n  "trailingComma": "all",\n  "printWidth": 100\n}\n'),

    ("chore", "chore: add example environment variables",
     ".env.example",
     "# MNMX Configuration\nMNMX_STRATEGY=minimax\nMNMX_MAX_HOPS=3\nMNMX_TIMEOUT=30000\nMNMX_SLIPPAGE=0.5\nMNMX_LOG_LEVEL=info\n\n# RPC Endpoints\nETH_RPC_URL=\nSOL_RPC_URL=\nARB_RPC_URL=\n"),

    ("chore", "chore: add code owners file",
     ".github/CODEOWNERS",
     "# Default code owners\n* @MEMX-labs\n\n# Engine core\n/engine/ @MEMX-labs\n\n# TypeScript SDK\n/src/ @MEMX-labs\n\n# Python SDK\n/sdk/python/ @MEMX-labs\n"),

    ("chore", "chore: add GitHub funding configuration",
     ".github/FUNDING.yml",
     "github: MEMX-labs\n"),

    ("chore", "chore: add editor configuration",
     ".editorconfig",
     "root = true\n\n[*]\nend_of_line = lf\ninsert_final_newline = true\ncharset = utf-8\nindent_style = space\nindent_size = 2\n\n[*.rs]\nindent_size = 4\n\n[*.py]\nindent_size = 4\n\n[Makefile]\nindent_style = tab\n"),

    ("chore", "chore: add code of conduct",
     "CODE_OF_CONDUCT.md",
     "# Contributor Covenant Code of Conduct\n\n## Our Pledge\n\nWe as members, contributors, and leaders pledge to make participation in our\ncommunity a harassment-free experience for everyone.\n\n## Our Standards\n\nExamples of behavior that contributes to a positive environment:\n\n- Using welcoming and inclusive language\n- Being respectful of differing viewpoints\n- Gracefully accepting constructive criticism\n- Focusing on what is best for the community\n\n## Enforcement\n\nInstances of abusive, harassing, or otherwise unacceptable behavior may be\nreported to the project team. All complaints will be reviewed and investigated.\n\n## Attribution\n\nThis Code of Conduct is adapted from the Contributor Covenant, version 2.1.\n"),

    ("chore", "chore: add markdown lint configuration",
     ".markdownlint.json",
     '{\n  "MD013": false,\n  "MD033": false,\n  "MD041": false\n}\n'),

    ("chore", "chore: add Python package manifest",
     "sdk/python/MANIFEST.in",
     "include LICENSE\ninclude README.md\nrecursive-include mnmx *.py py.typed\n"),

    ("fix", "fix(engine): define routing constants",
     "engine/src/constants.rs",
     "/// Maximum number of intermediate hops allowed in a route.\npub const MAX_HOPS: usize = 5;\n\n/// Default slippage tolerance in basis points.\npub const DEFAULT_SLIPPAGE_BPS: u64 = 50;\n\n/// Maximum route search timeout in milliseconds.\npub const MAX_TIMEOUT_MS: u64 = 30_000;\n\n/// Minimum bridge liquidity required for route consideration (USD).\npub const MIN_BRIDGE_LIQUIDITY: f64 = 10_000.0;\n\n/// Maximum number of concurrent bridge quote requests.\npub const MAX_CONCURRENT_QUOTES: usize = 10;\n\n/// Default adversarial slippage multiplier.\npub const DEFAULT_SLIPPAGE_MULTIPLIER: f64 = 2.0;\n\n/// Default adversarial gas multiplier.\npub const DEFAULT_GAS_MULTIPLIER: f64 = 1.5;\n\n/// Default bridge delay multiplier for worst-case estimation.\npub const DEFAULT_BRIDGE_DELAY_MULTIPLIER: f64 = 3.0;\n\n/// Maximum acceptable MEV extraction rate.\npub const MAX_MEV_RATE: f64 = 0.01;\n\n/// Score threshold below which routes are discarded.\npub const MIN_ROUTE_SCORE: f64 = 0.1;\n"),

    ("fix", "fix(engine): add custom error types",
     "engine/src/error.rs",
     'use thiserror::Error;\n\n/// Errors that can occur during route discovery and execution.\n#[derive(Error, Debug)]\npub enum MnmxError {\n    #[error("no viable route found between {from} and {to}")]\n    NoRouteFound { from: String, to: String },\n\n    #[error("insufficient liquidity on bridge {bridge}: need {required}, available {available}")]\n    InsufficientLiquidity {\n        bridge: String,\n        required: f64,\n        available: f64,\n    },\n\n    #[error("route search timed out after {elapsed_ms}ms (limit: {timeout_ms}ms)")]\n    SearchTimeout { elapsed_ms: u64, timeout_ms: u64 },\n\n    #[error("bridge {bridge} is currently offline or degraded")]\n    BridgeUnavailable { bridge: String },\n\n    #[error("invalid configuration: {reason}")]\n    InvalidConfig { reason: String },\n\n    #[error("scoring weights must sum to 1.0, got {sum}")]\n    InvalidWeights { sum: f64 },\n\n    #[error("chain {chain} is not supported")]\n    UnsupportedChain { chain: String },\n\n    #[error("execution failed at hop {hop}: {reason}")]\n    ExecutionFailed { hop: usize, reason: String },\n}\n\npub type Result<T> = std::result::Result<T, MnmxError>;\n'),

    ("fix", "fix: add SDK-level constants",
     "src/constants.ts",
     "/** Maximum number of hops allowed in a single route. */\nexport const MAX_HOPS = 5;\n\n/** Default route search timeout in milliseconds. */\nexport const DEFAULT_TIMEOUT_MS = 30_000;\n\n/** Default slippage tolerance in percentage. */\nexport const DEFAULT_SLIPPAGE_TOLERANCE = 0.5;\n\n/** Minimum bridge liquidity threshold in USD. */\nexport const MIN_BRIDGE_LIQUIDITY_USD = 10_000;\n\n/** Maximum concurrent bridge quote requests. */\nexport const MAX_CONCURRENT_QUOTES = 10;\n\n/** Score threshold below which routes are discarded. */\nexport const MIN_ROUTE_SCORE = 0.1;\n\n/** Maximum acceptable MEV extraction rate. */\nexport const MAX_MEV_RATE = 0.01;\n\n/** Bridge quote expiry time in milliseconds. */\nexport const QUOTE_EXPIRY_MS = 30_000;\n"),

    ("fix", "fix: add typed error classes for SDK",
     "src/errors.ts",
     "export class MnmxError extends Error {\n  constructor(message: string) {\n    super(message);\n    this.name = 'MnmxError';\n  }\n}\n\nexport class NoRouteFoundError extends MnmxError {\n  constructor(\n    public readonly fromChain: string,\n    public readonly toChain: string,\n  ) {\n    super(`No viable route found from ${fromChain} to ${toChain}`);\n    this.name = 'NoRouteFoundError';\n  }\n}\n\nexport class InsufficientLiquidityError extends MnmxError {\n  constructor(\n    public readonly bridge: string,\n    public readonly required: number,\n    public readonly available: number,\n  ) {\n    super(`Insufficient liquidity on ${bridge}: need ${required}, available ${available}`);\n    this.name = 'InsufficientLiquidityError';\n  }\n}\n\nexport class SearchTimeoutError extends MnmxError {\n  constructor(\n    public readonly elapsedMs: number,\n    public readonly timeoutMs: number,\n  ) {\n    super(`Route search timed out after ${elapsedMs}ms (limit: ${timeoutMs}ms)`);\n    this.name = 'SearchTimeoutError';\n  }\n}\n\nexport class BridgeUnavailableError extends MnmxError {\n  constructor(public readonly bridge: string) {\n    super(`Bridge ${bridge} is currently offline or degraded`);\n    this.name = 'BridgeUnavailableError';\n  }\n}\n"),

    ("fix", "fix(python): add input validators",
     "sdk/python/mnmx/validators.py",
     'from .types import RouterConfig, ScoringWeights\nfrom .exceptions import InvalidConfigError\n\n\ndef validate_config(config: RouterConfig) -> None:\n    """Validate router configuration values."""\n    if config.max_hops < 1 or config.max_hops > 5:\n        raise InvalidConfigError(f"max_hops must be 1-5, got {config.max_hops}")\n    if config.timeout_ms < 1000 or config.timeout_ms > 120_000:\n        raise InvalidConfigError(f"timeout_ms must be 1000-120000, got {config.timeout_ms}")\n    if config.slippage_tolerance < 0 or config.slippage_tolerance > 10:\n        raise InvalidConfigError(f"slippage_tolerance must be 0-10, got {config.slippage_tolerance}")\n    validate_weights(config.weights)\n\n\ndef validate_weights(weights: ScoringWeights) -> None:\n    """Validate that scoring weights sum to approximately 1.0."""\n    total = weights.fees + weights.slippage + weights.speed + weights.reliability + weights.mev_exposure\n    if abs(total - 1.0) > 0.01:\n        raise InvalidConfigError(f"Scoring weights must sum to 1.0, got {total:.4f}")\n    for name, val in [("fees", weights.fees), ("slippage", weights.slippage),\n                       ("speed", weights.speed), ("reliability", weights.reliability),\n                       ("mev_exposure", weights.mev_exposure)]:\n        if val < 0 or val > 1:\n            raise InvalidConfigError(f"Weight {name} must be 0-1, got {val}")\n\n\ndef validate_amount(amount: str) -> float:\n    """Validate and parse transfer amount string."""\n    try:\n        value = float(amount)\n    except ValueError:\n        raise InvalidConfigError(f"Invalid amount: {amount!r}")\n    if value <= 0:\n        raise InvalidConfigError(f"Amount must be positive, got {value}")\n    return value\n'),

    ("refactor", "refactor(engine): add version information",
     "engine/src/version.rs",
     '/// MNMX engine version.\npub const VERSION: &str = env!("CARGO_PKG_VERSION");\n\n/// Returns the engine version string.\npub fn engine_version() -> &\'static str {\n    VERSION\n}\n\n/// Returns build metadata.\npub fn build_info() -> BuildInfo {\n    BuildInfo {\n        version: VERSION,\n        rust_version: env!("CARGO_PKG_RUST_VERSION"),\n    }\n}\n\n/// Build metadata.\npub struct BuildInfo {\n    pub version: &\'static str,\n    pub rust_version: &\'static str,\n}\n'),

    ("refactor", "refactor: add SDK version module",
     "src/version.ts",
     "/** MNMX SDK version. */\nexport const VERSION = '0.1.0';\n\n/** Returns the SDK version string. */\nexport function getVersion(): string {\n  return VERSION;\n}\n\n/** Returns build information. */\nexport function getBuildInfo(): { version: string; nodeVersion: string } {\n  return {\n    version: VERSION,\n    nodeVersion: process.version,\n  };\n}\n"),

    ("refactor", "refactor(python): add version module",
     "sdk/python/mnmx/version.py",
     '__version__ = "0.1.0"\n__version_info__ = (0, 1, 0)\n\ndef get_version() -> str:\n    """Return the SDK version string."""\n    return __version__\n'),

    ("refactor", "refactor(python): add configuration helpers",
     "sdk/python/mnmx/config.py",
     'from .types import RouterConfig, ScoringWeights, AdversarialModel\n\n\nSTRATEGY_DEFAULTS = {\n    "minimax": ScoringWeights(fees=0.25, slippage=0.25, speed=0.15, reliability=0.20, mev_exposure=0.15),\n    "cheapest": ScoringWeights(fees=0.45, slippage=0.30, speed=0.05, reliability=0.10, mev_exposure=0.10),\n    "fastest": ScoringWeights(fees=0.10, slippage=0.15, speed=0.50, reliability=0.15, mev_exposure=0.10),\n    "safest": ScoringWeights(fees=0.10, slippage=0.15, speed=0.10, reliability=0.40, mev_exposure=0.25),\n}\n\nDEFAULT_ADVERSARIAL = AdversarialModel(\n    slippage_multiplier=2.0,\n    gas_multiplier=1.5,\n    bridge_delay_multiplier=3.0,\n    mev_extraction=0.003,\n    price_movement=0.005,\n)\n\n\ndef get_default_config(strategy: str = "minimax") -> RouterConfig:\n    """Return a default RouterConfig for the given strategy."""\n    weights = STRATEGY_DEFAULTS.get(strategy, STRATEGY_DEFAULTS["minimax"])\n    return RouterConfig(\n        strategy=strategy,\n        slippage_tolerance=0.5,\n        timeout_ms=30_000,\n        max_hops=3,\n        weights=weights,\n        adversarial_model=DEFAULT_ADVERSARIAL,\n    )\n'),

    ("refactor", "refactor(python): add general utility functions",
     "sdk/python/mnmx/utils.py",
     'import time\nimport hashlib\nfrom typing import Any\n\n\ndef generate_request_id() -> str:\n    """Generate a unique request identifier."""\n    timestamp = str(time.time_ns())\n    return hashlib.sha256(timestamp.encode()).hexdigest()[:16]\n\n\ndef format_amount(amount: float, decimals: int = 6) -> str:\n    """Format a token amount with the specified decimal places."""\n    return f"{amount:.{decimals}f}"\n\n\ndef parse_chain_token(spec: str) -> tuple[str, str, str]:\n    """Parse a chain:token:amount specification string."""\n    parts = spec.split(":")\n    if len(parts) != 3:\n        raise ValueError(f"Expected chain:token:amount format, got {spec!r}")\n    return parts[0], parts[1], parts[2]\n\n\ndef elapsed_ms(start_ns: int) -> float:\n    """Return elapsed milliseconds since start_ns."""\n    return (time.time_ns() - start_ns) / 1_000_000\n'),

    ("docs", "docs: add terminology glossary",
     "docs/GLOSSARY.md",
     "# Glossary\n\n## Alpha-Beta Pruning\nAn optimization technique for minimax search that eliminates branches\nthat cannot influence the final decision. Reduces search space by 90%+\nwithout affecting the optimal result.\n\n## Adversarial Model\nA mathematical model of worst-case market conditions used by the minimax\nengine to estimate the guaranteed minimum outcome of a route.\n\n## Bridge Adapter\nA modular integration layer that connects the MNMX routing engine to a\nspecific cross-chain bridge protocol (e.g., Wormhole, deBridge).\n\n## Guaranteed Minimum\nThe worst-case output of a route under the adversarial model. This is\nthe value that minimax optimization maximizes.\n\n## MEV (Maximal Extractable Value)\nValue that can be extracted from users by reordering, inserting, or\ncensoring transactions. MNMX models MEV as an adversarial cost.\n\n## Minimax\nA decision rule that minimizes the possible loss for a worst-case\nscenario. Originally from game theory, applied here to route selection.\n\n## Route Hop\nA single segment of a cross-chain route, typically involving one bridge\ntransfer between two chains.\n\n## Scoring Weights\nFive configurable parameters (fees, slippage, speed, reliability, MEV\nexposure) that control how routes are evaluated and compared.\n\n## Slippage\nThe difference between the expected output and the actual output of a\ntoken transfer, caused by price movement during execution.\n\n## Strategy Profile\nA preset configuration of scoring weights optimized for a specific use\ncase: minimax (default), cheapest, fastest, or safest.\n\n## Transposition Table\nA cache that stores previously evaluated positions to avoid redundant\ncomputation during minimax search.\n"),

    ("docs", "docs: add troubleshooting guide",
     "docs/TROUBLESHOOTING.md",
     "# Troubleshooting\n\n## No Route Found\n\n**Symptom:** `NoRouteFoundError` when calling `findRoute()` or `find_route()`.\n\n**Common causes:**\n- The source and destination chains have no bridge in common\n- Bridge liquidity is too low for the transfer amount\n- All bridges are currently offline or degraded\n- `maxHops` is set too low for the chain pair\n\n**Solutions:**\n1. Check supported chain pairs with `getSupportedChains()`\n2. Increase `maxHops` to allow indirect routing\n3. Reduce transfer amount\n4. Check bridge health with `getHealth()`\n\n## Search Timeout\n\n**Symptom:** `SearchTimeoutError` during route discovery.\n\n**Common causes:**\n- Transfer involves many possible paths (high branching factor)\n- Timeout is set too low\n- Bridge APIs are slow to respond\n\n**Solutions:**\n1. Increase `timeout` in router config\n2. Reduce `maxHops` to limit search space\n3. Exclude slow bridges with `excludeBridges`\n\n## High Slippage Warning\n\n**Symptom:** `guaranteedMinimum` is significantly lower than `expectedOutput`.\n\n**Common causes:**\n- Low liquidity on the selected bridge\n- Large transfer amount relative to pool depth\n- High market volatility\n\n**Solutions:**\n1. Use `safest` strategy for large transfers\n2. Split into multiple smaller transfers\n3. Increase `slippageTolerance` if the gap is acceptable\n"),

    ("docs", "docs: add performance optimization guide",
     "docs/PERFORMANCE.md",
     "# Performance Guide\n\n## Search Optimization\n\nThe minimax engine uses several techniques to search efficiently:\n\n### Alpha-Beta Pruning\nEliminates branches that cannot affect the result. Typically reduces\nthe search space by 90%+ compared to naive minimax.\n\n### Transposition Table\nCaches evaluated positions to avoid redundant computation. Most\neffective when multiple paths lead to the same intermediate state.\n\n### Move Ordering\nEvaluates the most promising routes first, maximizing pruning\nefficiency. Uses killer move heuristic and history table.\n\n### Iterative Deepening\nSearches progressively deeper, ensuring a valid result is always\navailable even if the search is interrupted by timeout.\n\n## Benchmarks\n\n| Operation | Typical Time | Notes |\n|-----------|-------------|-------|\n| Path discovery | <1ms | 8 chains, 4 bridges |\n| Minimax search (depth 3) | 1-5ms | With alpha-beta pruning |\n| Minimax search (depth 5) | 5-20ms | With transposition table |\n| Full route scoring | <0.1ms | Per route |\n| End-to-end routing | 5-30ms | Discovery + search + scoring |\n\n## Configuration Tips\n\n- Set `maxHops` to 2 for fast results, 3 for optimal results\n- Use `fastest` strategy when latency matters more than cost\n- Reduce `timeout` for real-time applications\n- Increase transposition table size for deep searches\n"),

    ("docs", "docs: add CHANGELOG",
     "CHANGELOG.md",
     "# Changelog\n\nAll notable changes to MNMX will be documented in this file.\n\nThe format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),\nand this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).\n\n## [Unreleased]\n\n### Added\n- Core minimax routing engine in Rust with alpha-beta pruning\n- TypeScript SDK with MnmxRouter, bridge adapters, and path discovery\n- Python SDK with route simulation, Monte Carlo analysis, and CLI\n- Bridge adapters: Wormhole, deBridge, LayerZero, Allbridge\n- Support for 8 chains\n- Four routing strategies: minimax, cheapest, fastest, safest\n- Five-dimensional route scoring\n- Adversarial model for worst-case estimation\n- Comprehensive test suites\n- CI/CD with GitHub Actions\n- Full documentation\n"),

    ("docs", "docs: add frequently asked questions",
     "docs/FAQ.md",
     "# FAQ\n\n## What is minimax optimization?\n\nMinimax is a decision strategy from game theory that finds the move\nwhich maximizes the minimum possible outcome. In routing terms: it\nfinds the route with the best worst-case result.\n\n## How is this different from other bridge aggregators?\n\nMost aggregators optimize for expected value (best average case).\nMNMX optimizes for guaranteed minimum (best worst case). This\nproduces more predictable outcomes, especially for large transfers.\n\n## Which chains are supported?\n\nEthereum, Solana, Arbitrum, Base, Polygon, BNB Chain, Optimism,\nand Avalanche.\n\n## Which bridges does MNMX use?\n\nWormhole, deBridge, LayerZero, and Allbridge. Custom bridges can\nbe added by implementing the BridgeAdapter interface.\n\n## Can I add my own bridge?\n\nYes. Implement the `BridgeAdapter` interface and register it with\n`router.registerBridge()`. See the Bridge Adapters documentation.\n\n## What are the strategy options?\n\n- **minimax** (default): Best guaranteed minimum outcome\n- **cheapest**: Lowest total fees\n- **fastest**: Shortest transfer time\n- **safest**: Highest bridge reliability\n"),

    ("style", "style: add Makefile for development workflow",
     "Makefile",
     ".PHONY: build test lint clean bench docs\n\nbuild:\n\tnpm run build\n\tcd engine && cargo build --release\n\ntest:\n\tnpm test\n\tcd engine && cargo test\n\tcd sdk/python && python -m pytest\n\nlint:\n\tnpm run lint\n\tcd engine && cargo clippy\n\nclean:\n\trm -rf dist/\n\tcd engine && cargo clean\n\nbench:\n\tcd engine && cargo bench\n"),

    ("style", "style: add PEP 561 type marker",
     "sdk/python/mnmx/py.typed", ""),

    ("style", "style: add stale issue configuration",
     ".github/stale.yml",
     "daysUntilStale: 60\ndaysUntilClose: 7\nexemptLabels:\n  - pinned\n  - security\n  - bug\nstaleLabel: stale\nmarkComment: >\n  This issue has been automatically marked as stale because it has not had\n  recent activity. It will be closed if no further activity occurs.\ncloseComment: false\n"),

    ("ci", "ci: add Cargo clippy to CI pipeline",
     ".github/workflows/clippy.yml",
     "name: Clippy\non:\n  push:\n    branches: [main]\n    paths: ['engine/**']\n  pull_request:\n    paths: ['engine/**']\njobs:\n  clippy:\n    runs-on: ubuntu-latest\n    steps:\n      - uses: actions/checkout@v4\n      - uses: dtolnay/rust-toolchain@stable\n        with:\n          components: clippy\n      - run: cd engine && cargo clippy -- -D warnings\n"),

    ("perf", "perf(engine): add route scoring cache hint",
     "engine/src/cache.rs",
     "use std::collections::HashMap;\n\n/// Simple LRU-style cache for route scoring results.\npub struct ScoreCache {\n    entries: HashMap<u64, f64>,\n    max_entries: usize,\n}\n\nimpl ScoreCache {\n    pub fn new(max_entries: usize) -> Self {\n        Self {\n            entries: HashMap::with_capacity(max_entries),\n            max_entries,\n        }\n    }\n\n    pub fn get(&self, key: u64) -> Option<f64> {\n        self.entries.get(&key).copied()\n    }\n\n    pub fn insert(&mut self, key: u64, score: f64) {\n        if self.entries.len() >= self.max_entries {\n            // Simple eviction: clear half the cache\n            let keys: Vec<u64> = self.entries.keys().take(self.max_entries / 2).copied().collect();\n            for k in keys {\n                self.entries.remove(&k);\n            }\n        }\n        self.entries.insert(key, score);\n    }\n\n    pub fn clear(&mut self) {\n        self.entries.clear();\n    }\n\n    pub fn len(&self) -> usize {\n        self.entries.len()\n    }\n\n    pub fn is_empty(&self) -> bool {\n        self.entries.is_empty()\n    }\n}\n"),

    ("perf", "perf: add chain config caching",
     "src/chains/cache.ts",
     "import type { Chain, ChainConfig } from '../types';\n\nconst configCache = new Map<Chain, ChainConfig>();\n\nexport function getCachedConfig(chain: Chain): ChainConfig | undefined {\n  return configCache.get(chain);\n}\n\nexport function setCachedConfig(chain: Chain, config: ChainConfig): void {\n  configCache.set(chain, config);\n}\n\nexport function clearConfigCache(): void {\n  configCache.clear();\n}\n\nexport function getConfigCacheSize(): number {\n  return configCache.size;\n}\n"),
]


# ============================================================
# MAIN PLAN with natural interleaving
# ============================================================

PLAN = [
    # === PHASE 1: Init (Jan 20-24) ===
    ("chore: initialize project with gitignore", [("f", ".gitignore")]),
    ("docs: add MIT license", [("f", "LICENSE")]),
    ("docs: add initial README", [("p", "README.md", 0.05)]),
    ("chore(engine): initialize Rust crate with Cargo.toml", [("f", "engine/Cargo.toml")]),
    ("feat(engine): define core type system", [("p", "engine/src/types.rs", 0.12), ("p", "engine/src/lib.rs", 0.2)]),
    ("feat(engine): add token and route hop types", [("p", "engine/src/types.rs", 0.22)]),
    ("BREAK", []),  # chore: Rust formatter
    ("feat(engine): add route and bridge quote types", [("p", "engine/src/types.rs", 0.35)]),
    ("feat(engine): add bridge health and status types", [("p", "engine/src/types.rs", 0.45)]),
    ("BREAK", []),  # chore: npm config
    ("feat(engine): add strategy enum and route request", [("p", "engine/src/types.rs", 0.6)]),
    ("feat(engine): add scoring weights and adversarial model", [("p", "engine/src/types.rs", 0.8)]),
    ("BREAK", []),  # chore: prettier
    ("feat(engine): add router config and default implementations", [("f", "engine/src/types.rs")]),
    ("feat(engine): add math utility functions", [("p", "engine/src/math.rs", 0.4)]),
    ("BREAK", []),  # chore: env example
    ("feat(engine): add normalization and statistical functions", [("p", "engine/src/math.rs", 0.7)]),
    ("feat(engine): complete math module with sigmoid and softmax", [("f", "engine/src/math.rs")]),
    ("chore: add TypeScript package.json and tsconfig", [("f", "package.json"), ("f", "tsconfig.json")]),
    ("chore: add vitest configuration", [("f", "vitest.config.ts")]),

    # === PHASE 2: Engine Core (Jan 25 - Feb 5) ===
    ("feat(engine): implement search statistics collector", [("p", "engine/src/stats.rs", 0.5)]),
    ("feat(engine): add branching factor and depth histogram to stats", [("f", "engine/src/stats.rs")]),
    ("BREAK", []),  # fix: routing constants
    ("feat(engine): define bridge adapter trait", [("p", "engine/src/bridge.rs", 0.2)]),
    ("feat(engine): add bridge capability matrix", [("p", "engine/src/bridge.rs", 0.4)]),
    ("BREAK", []),  # fix: error types
    ("feat(engine): implement bridge registry", [("p", "engine/src/bridge.rs", 0.65)]),
    ("feat(engine): add mock bridge adapter for testing", [("f", "engine/src/bridge.rs")]),
    ("BREAK", []),  # chore: CODEOWNERS
    ("feat(engine): add basic path discovery", [("p", "engine/src/path_discovery.rs", 0.2)]),
    ("feat(engine): implement direct path enumeration", [("p", "engine/src/path_discovery.rs", 0.4)]),
    ("BREAK", []),  # chore: funding
    ("feat(engine): add multi-hop path discovery", [("p", "engine/src/path_discovery.rs", 0.65)]),
    ("feat(engine): implement path deduplication and dominated filtering", [("f", "engine/src/path_discovery.rs")]),
    ("BREAK", []),  # chore: editorconfig
    ("feat(engine): implement base scoring function", [("p", "engine/src/scoring.rs", 0.2)]),
    ("feat(engine): add fee and slippage normalization", [("p", "engine/src/scoring.rs", 0.4)]),
    ("BREAK", []),  # chore: vscode extensions
    ("feat(engine): add speed and reliability normalization", [("p", "engine/src/scoring.rs", 0.6)]),
    ("feat(engine): implement route comparison logic", [("p", "engine/src/scoring.rs", 0.8)]),
    ("BREAK", []),  # chore: markdownlint
    ("feat(engine): add strategy weight presets", [("f", "engine/src/scoring.rs")]),
    ("feat(engine): implement alpha-beta pruning state", [("p", "engine/src/pruning.rs", 0.2)]),
    ("BREAK", []),  # chore: manifest.in
    ("feat(engine): add transposition table entry types", [("p", "engine/src/pruning.rs", 0.4)]),
    ("feat(engine): implement transposition table with replacement", [("p", "engine/src/pruning.rs", 0.65)]),
    ("BREAK", []),  # fix: SDK constants
    ("feat(engine): add killer move heuristic and move ordering", [("f", "engine/src/pruning.rs")]),
    ("feat(engine): implement chain state types", [("p", "engine/src/state.rs", 0.25)]),
    ("BREAK", []),  # fix: error classes
    ("feat(engine): add market state collector", [("p", "engine/src/state.rs", 0.55)]),
    ("feat(engine): add price and liquidity estimation", [("f", "engine/src/state.rs")]),
    ("BREAK", []),  # fix: validators
    ("feat(engine): add risk assessment types", [("p", "engine/src/risk.rs", 0.2)]),
    ("feat(engine): implement worst-case slippage and gas computation", [("p", "engine/src/risk.rs", 0.45)]),
    ("BREAK", []),  # refactor: engine version
    ("feat(engine): add MEV estimation model", [("p", "engine/src/risk.rs", 0.7)]),
    ("feat(engine): implement risk level classification", [("f", "engine/src/risk.rs")]),

    # === PHASE 3: Minimax + Router (Feb 6-14) ===
    ("BREAK", []),  # refactor: SDK version
    ("feat(engine): implement minimax search struct", [("p", "engine/src/minimax.rs", 0.15)]),
    ("feat(engine): add core minimax recursion", [("p", "engine/src/minimax.rs", 0.3)]),
    ("BREAK", []),  # refactor: Python version
    ("feat(engine): integrate alpha-beta pruning into search", [("p", "engine/src/minimax.rs", 0.45)]),
    ("feat(engine): add move generation for route candidates", [("p", "engine/src/minimax.rs", 0.6)]),
    ("BREAK", []),  # refactor: Python config
    ("feat(engine): implement iterative deepening", [("p", "engine/src/minimax.rs", 0.75)]),
    ("feat(engine): add adversarial model application to search", [("p", "engine/src/minimax.rs", 0.9)]),
    ("BREAK", []),  # refactor: Python utils
    ("feat(engine): complete minimax with transposition table integration", [("f", "engine/src/minimax.rs")]),
    ("feat(engine): implement router struct and constructor", [("p", "engine/src/router.rs", 0.25)]),
    ("BREAK", []),  # docs: glossary
    ("feat(engine): add route finding with bridge integration", [("p", "engine/src/router.rs", 0.5)]),
    ("feat(engine): add find_all_routes and strategy selection", [("p", "engine/src/router.rs", 0.75)]),
    ("BREAK", []),  # docs: troubleshooting
    ("feat(engine): complete router with config management", [("f", "engine/src/router.rs")]),
    ("chore(engine): update module declarations", [("f", "engine/src/lib.rs")]),

    # === PHASE 4: Rust Tests (Feb 14-17) ===
    ("test(engine): add basic minimax search test", [("p", "engine/tests/minimax_test.rs", 0.3)]),
    ("test(engine): add pruning efficiency and adversarial tests", [("p", "engine/tests/minimax_test.rs", 0.6)]),
    ("BREAK", []),  # docs: performance
    ("test(engine): add depth comparison and greedy comparison tests", [("f", "engine/tests/minimax_test.rs")]),
    ("test(engine): add scoring weight validation tests", [("p", "engine/tests/scoring_test.rs", 0.35)]),
    ("BREAK", []),  # docs: changelog
    ("test(engine): add strategy weights and normalization tests", [("p", "engine/tests/scoring_test.rs", 0.7)]),
    ("test(engine): add route comparison and bounded score tests", [("f", "engine/tests/scoring_test.rs")]),
    ("BREAK", []),  # docs: faq
    ("test(engine): add direct route discovery tests", [("p", "engine/tests/routing_test.rs", 0.3)]),
    ("test(engine): add multi-hop and filtering tests", [("p", "engine/tests/routing_test.rs", 0.6)]),
    ("BREAK", []),  # style: Makefile
    ("test(engine): add serialization and cross-VM routing tests", [("f", "engine/tests/routing_test.rs")]),
    ("perf(engine): add routing benchmarks", [("p", "engine/benches/routing_bench.rs", 0.5)]),
    ("BREAK", []),  # style: py.typed
    ("perf(engine): add minimax and scoring benchmarks", [("f", "engine/benches/routing_bench.rs")]),

    # === PHASE 5: TypeScript SDK Types & Utils (Feb 17-22) ===
    ("feat(types): define chain and token types", [("p", "src/types/index.ts", 0.12)]),
    ("feat(types): add route and route hop interfaces", [("p", "src/types/index.ts", 0.25)]),
    ("BREAK", []),  # style: stale config
    ("feat(types): add route request and options interfaces", [("p", "src/types/index.ts", 0.4)]),
    ("feat(types): add strategy, scoring weights, and adversarial model", [("p", "src/types/index.ts", 0.6)]),
    ("BREAK", []),  # ci: clippy
    ("feat(types): add bridge quote and health interfaces", [("p", "src/types/index.ts", 0.8)]),
    ("feat(types): add execution result, search stats, and config types", [("f", "src/types/index.ts")]),
    ("BREAK", []),  # perf: score cache
    ("feat(utils): implement logger with level filtering", [("p", "src/utils/logger.ts", 0.5)]),
    ("feat(utils): add child loggers and color support", [("f", "src/utils/logger.ts")]),
    ("BREAK", []),  # perf: chain cache
    ("feat(utils): add math utility functions", [("f", "src/utils/math.ts")]),
    ("feat(utils): add route hashing utilities", [("f", "src/utils/hash.ts")]),
    ("chore(chains): define chain configurations", [("p", "src/chains/index.ts", 0.4)]),
    ("feat(chains): add Ethereum chain config and tokens", [("f", "src/chains/ethereum.ts")]),
    ("feat(chains): add Solana chain config and tokens", [("f", "src/chains/solana.ts")]),
    ("chore(chains): add Arbitrum chain config and tokens", [("f", "src/chains/arbitrum.ts")]),
    ("refactor(chains): complete chain registry with lookup functions", [("f", "src/chains/index.ts")]),

    # === BRANCH: feature/bridge-adapters (Feb 22-25) ===
    ("branch", [("branch", "feature/bridge-adapters")]),
    ("feat(bridges): define bridge adapter interface", [("p", "src/bridges/adapter.ts", 0.3)]),
    ("feat(bridges): add abstract bridge adapter base class", [("p", "src/bridges/adapter.ts", 0.6)]),
    ("chore(bridges): implement bridge registry", [("f", "src/bridges/adapter.ts")]),
    ("feat(bridges): implement Wormhole adapter", [("p", "src/bridges/wormhole.ts", 0.4)]),
    ("feat(bridges): add Wormhole fee calculation and chain mapping", [("f", "src/bridges/wormhole.ts")]),
    ("fix(bridges): implement deBridge adapter with DLN model", [("p", "src/bridges/debridge.ts", 0.4)]),
    ("feat(bridges): complete deBridge with taker margin calculation", [("f", "src/bridges/debridge.ts")]),
    ("feat(bridges): implement LayerZero adapter", [("p", "src/bridges/layerzero.ts", 0.4)]),
    ("refactor(bridges): add LayerZero DVN fees and endpoint mapping", [("f", "src/bridges/layerzero.ts")]),
    ("feat(bridges): implement Allbridge adapter with pool math", [("p", "src/bridges/allbridge.ts", 0.4)]),
    ("feat(bridges): complete Allbridge with multi-messenger support", [("f", "src/bridges/allbridge.ts")]),
    ("chore(bridges): add bridge barrel exports", [("f", "src/bridges/index.ts")]),
    ("merge", [("merge", "feature/bridge-adapters", "Merge pull request #1 from MEMX-labs/feature/bridge-adapters")]),

    # === PHASE 6: TypeScript Router (Feb 26 - Mar 2) ===
    ("feat(router): implement path discovery base", [("p", "src/router/path-discovery.ts", 0.2)]),
    ("feat(router): add DFS chain path enumeration", [("p", "src/router/path-discovery.ts", 0.4)]),
    ("refactor(router): add bridge combination expansion", [("p", "src/router/path-discovery.ts", 0.65)]),
    ("feat(router): add dominated path filtering and deduplication", [("f", "src/router/path-discovery.ts")]),
    ("feat(router): implement route scorer base", [("p", "src/router/scoring.ts", 0.3)]),
    ("fix(router): add normalization functions for scoring dimensions", [("p", "src/router/scoring.ts", 0.6)]),
    ("feat(router): add strategy presets and route comparison", [("f", "src/router/scoring.ts")]),
    ("refactor(router): scaffold minimax search engine struct", [("p", "src/router/minimax.ts", 0.2)]),
    ("feat(router): add core minimax with alpha-beta", [("p", "src/router/minimax.ts", 0.4)]),
    ("refactor(router): add adversarial scenario generation", [("p", "src/router/minimax.ts", 0.65)]),
    ("feat(router): add iterative deepening with severity scaling", [("f", "src/router/minimax.ts")]),
    ("chore(router): scaffold MnmxRouter class structure", [("p", "src/router/index.ts", 0.2)]),
    ("feat(router): add route finding logic", [("p", "src/router/index.ts", 0.4)]),
    ("fix(router): add route execution with progress events", [("p", "src/router/index.ts", 0.6)]),
    ("feat(router): add bridge management and config updates", [("p", "src/router/index.ts", 0.8)]),
    ("feat(router): complete router with validation and strategy selection", [("f", "src/router/index.ts")]),
    ("chore: add main package exports", [("f", "src/index.ts")]),

    # === PHASE 7: TypeScript Tests (Mar 2-4) ===
    ("test(router): add path discovery tests", [("p", "tests/router/path-discovery.test.ts", 0.5)]),
    ("test(router): add multi-hop and constraint tests", [("f", "tests/router/path-discovery.test.ts")]),
    ("fix(router): add minimax search tests", [("p", "tests/router/minimax.test.ts", 0.5)]),
    ("test(router): add pruning and adversarial tests", [("f", "tests/router/minimax.test.ts")]),
    ("test(router): add scoring function tests", [("p", "tests/router/scoring.test.ts", 0.5)]),
    ("refactor(scoring): add strategy presets and comparison tests", [("f", "tests/router/scoring.test.ts")]),
    ("test(bridges): add Wormhole adapter tests", [("f", "tests/bridges/wormhole.test.ts")]),
    ("fix(bridges): verify deBridge adapter behavior", [("f", "tests/bridges/debridge.test.ts")]),
    ("test: add end-to-end integration tests", [("p", "tests/integration/end-to-end.test.ts", 0.5)]),
    ("fix: add strategy comparison and bridge exclusion e2e tests", [("f", "tests/integration/end-to-end.test.ts")]),

    # === BRANCH: feature/python-sdk (Mar 4-8) ===
    ("branch", [("branch", "feature/python-sdk")]),
    ("chore(python): initialize Python SDK with pyproject.toml", [("f", "sdk/python/pyproject.toml")]),
    ("feat(python): define exception hierarchy", [("f", "sdk/python/mnmx/exceptions.py")]),
    ("chore(python): add math utility functions", [("f", "sdk/python/mnmx/math_utils.py")]),
    ("feat(python): define core chain and token types", [("p", "sdk/python/mnmx/types.py", 0.2)]),
    ("feat(python): add route and bridge quote types", [("p", "sdk/python/mnmx/types.py", 0.45)]),
    ("refactor(python): add config, scoring weights, and simulation types", [("p", "sdk/python/mnmx/types.py", 0.7)]),
    ("feat(python): add Monte Carlo result and search stats types", [("f", "sdk/python/mnmx/types.py")]),
    ("feat(python): implement Wormhole and deBridge adapters", [("p", "sdk/python/mnmx/bridges.py", 0.35)]),
    ("fix(python): add LayerZero and Allbridge adapters", [("p", "sdk/python/mnmx/bridges.py", 0.7)]),
    ("feat(python): add bridge registry and chain support matrix", [("f", "sdk/python/mnmx/bridges.py")]),
    ("feat(python): implement route scoring function", [("p", "sdk/python/mnmx/scoring.py", 0.5)]),
    ("refactor(python): add strategy weight presets to scorer", [("f", "sdk/python/mnmx/scoring.py")]),
    ("feat(python): implement router with path discovery", [("p", "sdk/python/mnmx/router.py", 0.25)]),
    ("feat(python): add minimax search to router", [("p", "sdk/python/mnmx/router.py", 0.5)]),
    ("fix(python): add alpha-beta pruning and adversarial model", [("p", "sdk/python/mnmx/router.py", 0.75)]),
    ("feat(python): complete router with strategy selection and config", [("f", "sdk/python/mnmx/router.py")]),
    ("feat(python): implement route simulator", [("p", "sdk/python/mnmx/simulator.py", 0.35)]),
    ("refactor(python): add Monte Carlo analysis to simulator", [("p", "sdk/python/mnmx/simulator.py", 0.7)]),
    ("feat(python): add stress testing scenarios", [("f", "sdk/python/mnmx/simulator.py")]),
    ("feat(python): implement batch analyzer", [("p", "sdk/python/mnmx/batch_analyzer.py", 0.4)]),
    ("fix(python): add batch report and summary formatting", [("f", "sdk/python/mnmx/batch_analyzer.py")]),
    ("feat(python): implement CLI route command", [("p", "sdk/python/mnmx/cli.py", 0.3)]),
    ("refactor(python): add compare and simulate CLI commands", [("p", "sdk/python/mnmx/cli.py", 0.65)]),
    ("feat(python): add bridges and chains CLI commands", [("f", "sdk/python/mnmx/cli.py")]),
    ("chore(python): add package exports", [("f", "sdk/python/mnmx/__init__.py")]),
    ("merge", [("merge", "feature/python-sdk", "Merge pull request #2 from MEMX-labs/feature/python-sdk")]),

    # === BRANCH: fix/route-scoring-edge-cases (Mar 8-9) ===
    ("branch", [("branch", "fix/route-scoring-edge-cases")]),
    ("chore(python): add test fixtures and conftest", [("f", "sdk/python/tests/__init__.py"), ("f", "sdk/python/tests/conftest.py")]),
    ("test(python): add router tests", [("f", "sdk/python/tests/test_router.py")]),
    ("test(python): add simulator and Monte Carlo tests", [("f", "sdk/python/tests/test_simulator.py")]),
    ("fix(python): add bridge adapter tests", [("f", "sdk/python/tests/test_bridges.py")]),
    ("test(python): add batch analyzer tests", [("f", "sdk/python/tests/test_batch_analyzer.py")]),
    ("merge", [("merge", "fix/route-scoring-edge-cases", "Merge pull request #3 from MEMX-labs/fix/route-scoring-edge-cases")]),

    # === BRANCH: refactor/path-discovery-optimization (Mar 9-10) ===
    ("branch", [("branch", "refactor/path-discovery-optimization")]),
    ("feat: add basic route example", [("f", "examples/basic-route.ts")]),
    ("docs: add strategy comparison example", [("f", "examples/compare-strategies.ts")]),
    ("feat: add custom bridge adapter example", [("f", "examples/custom-bridge.ts")]),
    ("perf: add benchmark script", [("f", "scripts/benchmark.ts")]),
    ("merge", [("merge", "refactor/path-discovery-optimization", "Merge pull request #4 from MEMX-labs/refactor/path-discovery-optimization")]),

    # === PHASE 9: Documentation (Mar 10-12) ===
    ("docs: add architecture documentation", [("f", "docs/architecture.md")]),
    ("docs: add routing engine deep dive", [("f", "docs/routing-engine.md")]),
    ("chore: add minimax algorithm explanation", [("f", "docs/minimax-algorithm.md")]),
    ("docs: add bridge adapters documentation", [("f", "docs/bridge-adapters.md")]),
    ("docs: add Python SDK documentation", [("f", "docs/python-sdk.md")]),
    ("chore: add documentation index", [("f", "docs/README.md")]),
    ("docs: add comprehensive technical documentation", [("f", "CONTRIBUTING.md")]),

    # === BRANCH: feature/ci-community-standards (Mar 12-13) ===
    ("branch", [("branch", "feature/ci-community-standards")]),
    ("ci: add GitHub Actions CI workflow", [("f", ".github/workflows/ci.yml")]),
    ("chore: add issue templates", [("f", ".github/ISSUE_TEMPLATE/bug_report.md"), ("f", ".github/ISSUE_TEMPLATE/feature_request.md")]),
    ("docs: add pull request template", [("f", ".github/pull_request_template.md")]),
    ("chore: add dependabot configuration", [("f", ".github/dependabot.yml")]),
    ("docs: add security policy", [("f", "SECURITY.md")]),
    ("merge", [("merge", "feature/ci-community-standards", "Merge pull request #5 from MEMX-labs/feature/ci-community-standards")]),

    # === PHASE 10: Polish (Mar 13-15) ===
    ("chore: add banner image", [("b", "assets/banner.png")]),
    ("docs: update README with project overview", [("p", "README.md", 0.2)]),
    ("refactor: add architecture diagram to README", [("p", "README.md", 0.4)]),
    ("docs: add usage examples to README", [("p", "README.md", 0.6)]),
    ("fix: add strategy profiles and API reference to README", [("p", "README.md", 0.8)]),
    ("docs: complete README with all sections", [("f", "README.md")]),
]


def expand_breaks(plan):
    """Replace BREAK entries with actual break commits from the pool."""
    result = []
    break_idx = 0
    for msg, ops in plan:
        if msg == "BREAK":
            if break_idx < len(BREAK_POOL):
                prefix, bmsg, bpath, bcontent = BREAK_POOL[break_idx]
                result.append((bmsg, [("w", bpath, bcontent)]))
                break_idx += 1
        else:
            result.append((msg, ops))
    return result


def execute_plan():
    plan = expand_breaks(PLAN)

    # Count commits
    commit_entries = [e for e in plan if e[0] not in ("branch", "merge")]
    merge_entries = [e for e in plan if e[0] == "merge"]
    total = len(commit_entries) + len(merge_entries)
    print(f"Total commits planned: {total}")

    # Verify prefix diversity
    prefixes = [get_prefix(msg) for msg, _ in plan if msg not in ("branch", "merge")]
    consecutive = 1
    max_consecutive = 1
    max_prefix = prefixes[0]
    for i in range(1, len(prefixes)):
        if prefixes[i] == prefixes[i-1]:
            consecutive += 1
            if consecutive > max_consecutive:
                max_consecutive = consecutive
                max_prefix = prefixes[i]
        else:
            consecutive = 1
    print(f"Max consecutive same prefix: {max_consecutive} ({max_prefix})")

    # Generate dates
    start = datetime(2026, 1, 20, 10, 55, 7)
    end = datetime(2026, 3, 15, 19, 25, 54)
    dates = generate_dates(start, end, total)

    # Remove existing git
    git_dir = os.path.join(REPO, ".git")
    if os.path.exists(git_dir):
        print("Removing .git...")
        shutil.rmtree(git_dir, onexc=remove_readonly)

    # Clean working directory
    for item in os.listdir(REPO):
        if item in ('.backup', 'generate_history.py', 'generate_history_v2.py',
                     'add_commits.py', 'node_modules', '.git'):
            continue
        path = os.path.join(REPO, item)
        if os.path.isdir(path):
            shutil.rmtree(path, onexc=remove_readonly)
        else:
            os.remove(path)

    # Init fresh repo
    run("git init")
    run("git checkout -b main")

    date_idx = 0
    for msg, ops in plan:
        if msg == "branch":
            branch_name = ops[0][1]
            run(f"git checkout -b {branch_name}")
            continue

        if msg == "merge":
            _, branch_name, merge_msg = ops[0]
            dt = dates[date_idx]
            date_idx += 1
            run("git checkout main")
            git_merge(branch_name, merge_msg, dt)
            print(f"  [{date_idx}/{total}] MERGE: {merge_msg[:60]}")
            continue

        for op in ops:
            if op[0] == "f":
                copy_file(op[1])
            elif op[0] == "p":
                copy_partial(op[1], op[2])
            elif op[0] == "b":
                copy_file(op[1])
            elif op[0] == "w":
                write_file(op[1], op[2])

        dt = dates[date_idx]
        date_idx += 1
        ok = git_commit(msg, dt)
        status = "OK" if ok else "SKIP"
        print(f"  [{date_idx}/{total}] {dt.strftime('%m-%d %H:%M')} {status}: {msg[:70]}")

    print(f"\nDone! Created {date_idx} commits")


if __name__ == "__main__":
    execute_plan()
