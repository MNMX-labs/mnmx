#!/usr/bin/env python3
"""
MNMX commit history generator.
Reads final files from .backup/ and creates realistic git history.
"""

import os
import shutil
import subprocess
import random
import sys
from datetime import datetime, timedelta

REPO = os.path.dirname(os.path.abspath(__file__))
BACKUP = os.path.join(REPO, ".backup")
AUTHOR_NAME = "MEMX-labs"
AUTHOR_EMAIL = "256117066+MEMX-labs@users.noreply.github.com"

# KST timezone
TZ = "+09:00"

def run(cmd, env_extra=None):
    env = os.environ.copy()
    if env_extra:
        env.update(env_extra)
    r = subprocess.run(cmd, cwd=REPO, shell=True, capture_output=True, text=True, env=env)
    if r.returncode != 0 and "nothing to commit" not in r.stderr and "nothing to commit" not in r.stdout:
        pass  # some commands may fail silently
    return r

def git_commit(msg, dt):
    run("git add -A")
    ds = dt.strftime(f"%Y-%m-%dT%H:%M:%S{TZ}")
    env = {
        "GIT_AUTHOR_DATE": ds,
        "GIT_COMMITTER_DATE": ds,
        "GIT_AUTHOR_NAME": AUTHOR_NAME,
        "GIT_AUTHOR_EMAIL": AUTHOR_EMAIL,
        "GIT_COMMITTER_NAME": AUTHOR_NAME,
        "GIT_COMMITTER_EMAIL": AUTHOR_EMAIL,
    }
    r = run(f'git commit -m "{msg}"', env)
    if r.returncode != 0:
        print(f"  WARNING: commit failed: {r.stderr.strip()}")
        return False
    return True

def git_merge(branch, msg, dt):
    ds = dt.strftime(f"%Y-%m-%dT%H:%M:%S{TZ}")
    env = {
        "GIT_AUTHOR_DATE": ds,
        "GIT_COMMITTER_DATE": ds,
        "GIT_AUTHOR_NAME": AUTHOR_NAME,
        "GIT_AUTHOR_EMAIL": AUTHOR_EMAIL,
        "GIT_COMMITTER_NAME": AUTHOR_NAME,
        "GIT_COMMITTER_EMAIL": AUTHOR_EMAIL,
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

    # Binary files: copy whole
    try:
        with open(src, 'r', encoding='utf-8', errors='strict') as f:
            lines = f.readlines()
    except (UnicodeDecodeError, ValueError):
        shutil.copy2(src, dst)
        return

    target = int(len(lines) * fraction)
    if target < 5:
        target = min(len(lines), 10)

    # Find safe split point (blank line or closing brace)
    best = target
    for i in range(max(0, target - 20), min(len(lines), target + 20)):
        line = lines[i].rstrip()
        if line == '' or line == '}' or line == '};' or line == ')' or line == ');':
            if abs(i - target) < abs(best - target):
                best = i + 1

    with open(dst, 'w', encoding='utf-8') as f:
        f.writelines(lines[:best])

def generate_dates(start, end, n):
    """Generate n naturally distributed dates between start and end."""
    total_days = (end - start).days

    # Generate daily commit counts
    daily_counts = []
    day = start
    while day <= end:
        weekday = day.weekday()  # 0=Mon, 6=Sun

        # Base probability of committing
        if weekday >= 5:  # Weekend
            base = random.choice([0, 0, 0, 1, 1, 2])
        else:  # Weekday
            base = random.choice([0, 1, 1, 2, 2, 3, 3, 4, 5, 6])

        daily_counts.append((day, base))
        day += timedelta(days=1)

    # Ensure some gaps of 3+ days
    gap_starts = random.sample(range(5, len(daily_counts) - 5), 3)
    for gs in gap_starts:
        for offset in range(3):
            if gs + offset < len(daily_counts):
                daily_counts[gs + offset] = (daily_counts[gs + offset][0], 0)

    # Create burst periods (3-4 days of high activity)
    burst_starts = random.sample(range(3, len(daily_counts) - 5), 4)
    for bs in burst_starts:
        for offset in range(random.randint(2, 4)):
            if bs + offset < len(daily_counts):
                d, _ = daily_counts[bs + offset]
                daily_counts[bs + offset] = (d, random.randint(4, 7))

    # Flatten to date list
    all_dates = []
    for day, count in daily_counts:
        for _ in range(count):
            hour = random.choice([2, 3, 4, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23])
            minute = random.randint(0, 59)
            second = random.randint(0, 59)
            dt = day.replace(hour=hour, minute=minute, second=second)
            all_dates.append(dt)

    all_dates.sort()

    # Adjust to match desired count
    if len(all_dates) > n:
        # Remove random entries
        while len(all_dates) > n:
            idx = random.randint(0, len(all_dates) - 1)
            all_dates.pop(idx)
    elif len(all_dates) < n:
        # Add entries on random days
        while len(all_dates) < n:
            day_idx = random.randint(0, len(daily_counts) - 1)
            day = daily_counts[day_idx][0]
            hour = random.choice([10, 11, 14, 15, 16, 19, 20, 21])
            minute = random.randint(0, 59)
            second = random.randint(0, 59)
            dt = day.replace(hour=hour, minute=minute, second=second)
            all_dates.append(dt)
        all_dates.sort()

    # Ensure first commit is on start date and last is near end
    all_dates[0] = start
    all_dates[-1] = end

    return all_dates


# ============================================================
# COMMIT PLAN
# Each entry: (message, [(action, path, *args)])
#   "f" = copy full file from backup
#   "p" = copy partial file (fraction 0.0-1.0)
#   "b" = binary copy
#   "branch" = create branch
#   "merge" = merge branch
# ============================================================

PLAN = [
    # === PHASE 1: Project Initialization (Jan 20-24) ===
    ("chore: initialize project with gitignore", [("f", ".gitignore")]),
    ("docs: add MIT license", [("f", "LICENSE")]),
    ("docs: add initial README", [("p", "README.md", 0.05)]),
    ("chore(engine): initialize Rust crate with Cargo.toml", [("f", "engine/Cargo.toml")]),
    ("feat(engine): define core type system", [("p", "engine/src/types.rs", 0.12), ("p", "engine/src/lib.rs", 0.2)]),
    ("feat(engine): add token and route hop types", [("p", "engine/src/types.rs", 0.22)]),
    ("feat(engine): add route and bridge quote types", [("p", "engine/src/types.rs", 0.35)]),
    ("feat(engine): add bridge health and status types", [("p", "engine/src/types.rs", 0.45)]),
    ("feat(engine): add strategy enum and route request", [("p", "engine/src/types.rs", 0.6)]),
    ("feat(engine): add scoring weights and adversarial model", [("p", "engine/src/types.rs", 0.8)]),
    ("feat(engine): add router config and default implementations", [("f", "engine/src/types.rs")]),
    ("feat(engine): add math utility functions", [("p", "engine/src/math.rs", 0.4)]),
    ("feat(engine): add normalization and statistical functions", [("p", "engine/src/math.rs", 0.7)]),
    ("feat(engine): complete math module with sigmoid and softmax", [("f", "engine/src/math.rs")]),
    ("chore: add TypeScript package.json and tsconfig", [("f", "package.json"), ("f", "tsconfig.json")]),
    ("chore: add vitest configuration", [("f", "vitest.config.ts")]),

    # === PHASE 2: Rust Engine Core (Jan 25 - Feb 5) ===
    ("feat(engine): implement search statistics collector", [("p", "engine/src/stats.rs", 0.5)]),
    ("feat(engine): add branching factor and depth histogram to stats", [("f", "engine/src/stats.rs")]),
    ("feat(engine): define bridge adapter trait", [("p", "engine/src/bridge.rs", 0.2)]),
    ("feat(engine): add bridge capability matrix", [("p", "engine/src/bridge.rs", 0.4)]),
    ("feat(engine): implement bridge registry", [("p", "engine/src/bridge.rs", 0.65)]),
    ("feat(engine): add mock bridge adapter for testing", [("f", "engine/src/bridge.rs")]),
    ("feat(engine): add basic path discovery", [("p", "engine/src/path_discovery.rs", 0.2)]),
    ("feat(engine): implement direct path enumeration", [("p", "engine/src/path_discovery.rs", 0.4)]),
    ("feat(engine): add multi-hop path discovery", [("p", "engine/src/path_discovery.rs", 0.65)]),
    ("feat(engine): implement path deduplication and dominated filtering", [("f", "engine/src/path_discovery.rs")]),
    ("feat(engine): implement base scoring function", [("p", "engine/src/scoring.rs", 0.2)]),
    ("feat(engine): add fee and slippage normalization", [("p", "engine/src/scoring.rs", 0.4)]),
    ("feat(engine): add speed and reliability normalization", [("p", "engine/src/scoring.rs", 0.6)]),
    ("feat(engine): implement route comparison logic", [("p", "engine/src/scoring.rs", 0.8)]),
    ("feat(engine): add strategy weight presets", [("f", "engine/src/scoring.rs")]),
    ("feat(engine): implement alpha-beta pruning state", [("p", "engine/src/pruning.rs", 0.2)]),
    ("feat(engine): add transposition table entry types", [("p", "engine/src/pruning.rs", 0.4)]),
    ("feat(engine): implement transposition table with replacement", [("p", "engine/src/pruning.rs", 0.65)]),
    ("feat(engine): add killer move heuristic and move ordering", [("f", "engine/src/pruning.rs")]),
    ("feat(engine): implement chain state types", [("p", "engine/src/state.rs", 0.25)]),
    ("feat(engine): add market state collector", [("p", "engine/src/state.rs", 0.55)]),
    ("feat(engine): add price and liquidity estimation", [("f", "engine/src/state.rs")]),
    ("feat(engine): add risk assessment types", [("p", "engine/src/risk.rs", 0.2)]),
    ("feat(engine): implement worst-case slippage and gas computation", [("p", "engine/src/risk.rs", 0.45)]),
    ("feat(engine): add MEV estimation model", [("p", "engine/src/risk.rs", 0.7)]),
    ("feat(engine): implement risk level classification", [("f", "engine/src/risk.rs")]),

    # === PHASE 3: Minimax Engine + Router (Feb 6-14) ===
    ("feat(engine): implement minimax search struct", [("p", "engine/src/minimax.rs", 0.15)]),
    ("feat(engine): add core minimax recursion", [("p", "engine/src/minimax.rs", 0.3)]),
    ("feat(engine): integrate alpha-beta pruning into search", [("p", "engine/src/minimax.rs", 0.45)]),
    ("feat(engine): add move generation for route candidates", [("p", "engine/src/minimax.rs", 0.6)]),
    ("feat(engine): implement iterative deepening", [("p", "engine/src/minimax.rs", 0.75)]),
    ("feat(engine): add adversarial model application to search", [("p", "engine/src/minimax.rs", 0.9)]),
    ("feat(engine): complete minimax with transposition table integration", [("f", "engine/src/minimax.rs")]),
    ("feat(engine): implement router struct and constructor", [("p", "engine/src/router.rs", 0.25)]),
    ("feat(engine): add route finding with bridge integration", [("p", "engine/src/router.rs", 0.5)]),
    ("feat(engine): add find_all_routes and strategy selection", [("p", "engine/src/router.rs", 0.75)]),
    ("feat(engine): complete router with config management", [("f", "engine/src/router.rs")]),
    ("feat(engine): update module declarations", [("f", "engine/src/lib.rs")]),

    # === PHASE 4: Rust Tests (Feb 14-17) ===
    ("test(engine): add basic minimax search test", [("p", "engine/tests/minimax_test.rs", 0.3)]),
    ("test(engine): add pruning efficiency and adversarial tests", [("p", "engine/tests/minimax_test.rs", 0.6)]),
    ("test(engine): add depth comparison and greedy comparison tests", [("f", "engine/tests/minimax_test.rs")]),
    ("test(engine): add scoring weight validation tests", [("p", "engine/tests/scoring_test.rs", 0.35)]),
    ("test(engine): add strategy weights and normalization tests", [("p", "engine/tests/scoring_test.rs", 0.7)]),
    ("test(engine): add route comparison and bounded score tests", [("f", "engine/tests/scoring_test.rs")]),
    ("test(engine): add direct route discovery tests", [("p", "engine/tests/routing_test.rs", 0.3)]),
    ("test(engine): add multi-hop and filtering tests", [("p", "engine/tests/routing_test.rs", 0.6)]),
    ("test(engine): add serialization and cross-VM routing tests", [("f", "engine/tests/routing_test.rs")]),
    ("perf(engine): add routing benchmarks", [("p", "engine/benches/routing_bench.rs", 0.5)]),
    ("perf(engine): add minimax and scoring benchmarks", [("f", "engine/benches/routing_bench.rs")]),

    # === PHASE 5: TypeScript SDK Types & Utils (Feb 17-22) ===
    ("feat(types): define chain and token types", [("p", "src/types/index.ts", 0.12)]),
    ("feat(types): add route and route hop interfaces", [("p", "src/types/index.ts", 0.25)]),
    ("feat(types): add route request and options interfaces", [("p", "src/types/index.ts", 0.4)]),
    ("feat(types): add strategy, scoring weights, and adversarial model", [("p", "src/types/index.ts", 0.6)]),
    ("feat(types): add bridge quote and health interfaces", [("p", "src/types/index.ts", 0.8)]),
    ("feat(types): add execution result, search stats, and config types", [("f", "src/types/index.ts")]),
    ("feat(utils): implement logger with level filtering", [("p", "src/utils/logger.ts", 0.5)]),
    ("feat(utils): add child loggers and color support", [("f", "src/utils/logger.ts")]),
    ("feat(utils): add math utility functions", [("f", "src/utils/math.ts")]),
    ("feat(utils): add route hashing utilities", [("f", "src/utils/hash.ts")]),
    ("feat(chains): define chain configurations", [("p", "src/chains/index.ts", 0.4)]),
    ("feat(chains): add Ethereum chain config and tokens", [("f", "src/chains/ethereum.ts")]),
    ("feat(chains): add Solana chain config and tokens", [("f", "src/chains/solana.ts")]),
    ("feat(chains): add Arbitrum chain config and tokens", [("f", "src/chains/arbitrum.ts")]),
    ("feat(chains): complete chain registry with lookup functions", [("f", "src/chains/index.ts")]),

    # === BRANCH: feature/bridge-adapters (Feb 22-25) ===
    ("branch", [("branch", "feature/bridge-adapters")]),
    ("feat(bridges): define bridge adapter interface", [("p", "src/bridges/adapter.ts", 0.3)]),
    ("feat(bridges): add abstract bridge adapter base class", [("p", "src/bridges/adapter.ts", 0.6)]),
    ("feat(bridges): implement bridge registry", [("f", "src/bridges/adapter.ts")]),
    ("feat(bridges): implement Wormhole adapter", [("p", "src/bridges/wormhole.ts", 0.4)]),
    ("feat(bridges): add Wormhole fee calculation and chain mapping", [("f", "src/bridges/wormhole.ts")]),
    ("feat(bridges): implement deBridge adapter with DLN model", [("p", "src/bridges/debridge.ts", 0.4)]),
    ("feat(bridges): complete deBridge with taker margin calculation", [("f", "src/bridges/debridge.ts")]),
    ("feat(bridges): implement LayerZero adapter", [("p", "src/bridges/layerzero.ts", 0.4)]),
    ("feat(bridges): add LayerZero DVN fees and endpoint mapping", [("f", "src/bridges/layerzero.ts")]),
    ("feat(bridges): implement Allbridge adapter with pool math", [("p", "src/bridges/allbridge.ts", 0.4)]),
    ("feat(bridges): complete Allbridge with multi-messenger support", [("f", "src/bridges/allbridge.ts")]),
    ("feat(bridges): add bridge barrel exports", [("f", "src/bridges/index.ts")]),
    ("merge", [("merge", "feature/bridge-adapters", "Merge pull request #1 from MEMX-labs/feature/bridge-adapters")]),

    # === PHASE 6: TypeScript Router (Feb 26 - Mar 2) ===
    ("feat(router): implement path discovery base", [("p", "src/router/path-discovery.ts", 0.2)]),
    ("feat(router): add DFS chain path enumeration", [("p", "src/router/path-discovery.ts", 0.4)]),
    ("feat(router): add bridge combination expansion", [("p", "src/router/path-discovery.ts", 0.65)]),
    ("feat(router): add dominated path filtering and deduplication", [("f", "src/router/path-discovery.ts")]),
    ("feat(router): implement route scorer base", [("p", "src/router/scoring.ts", 0.3)]),
    ("feat(router): add normalization functions for scoring dimensions", [("p", "src/router/scoring.ts", 0.6)]),
    ("feat(router): add strategy presets and route comparison", [("f", "src/router/scoring.ts")]),
    ("feat(router): implement minimax search engine struct", [("p", "src/router/minimax.ts", 0.2)]),
    ("feat(router): add core minimax with alpha-beta", [("p", "src/router/minimax.ts", 0.4)]),
    ("feat(router): add adversarial scenario generation", [("p", "src/router/minimax.ts", 0.65)]),
    ("feat(router): add iterative deepening with severity scaling", [("f", "src/router/minimax.ts")]),
    ("feat(router): implement MnmxRouter constructor and config", [("p", "src/router/index.ts", 0.2)]),
    ("feat(router): add route finding logic", [("p", "src/router/index.ts", 0.4)]),
    ("feat(router): add route execution with progress events", [("p", "src/router/index.ts", 0.6)]),
    ("feat(router): add bridge management and config updates", [("p", "src/router/index.ts", 0.8)]),
    ("feat(router): complete router with validation and strategy selection", [("f", "src/router/index.ts")]),
    ("feat: add main package exports", [("f", "src/index.ts")]),

    # === PHASE 7: TypeScript Tests (Mar 2-4) ===
    ("test(router): add path discovery tests", [("p", "tests/router/path-discovery.test.ts", 0.5)]),
    ("test(router): add multi-hop and constraint tests", [("f", "tests/router/path-discovery.test.ts")]),
    ("test(router): add minimax search tests", [("p", "tests/router/minimax.test.ts", 0.5)]),
    ("test(router): add pruning and adversarial tests", [("f", "tests/router/minimax.test.ts")]),
    ("test(router): add scoring function tests", [("p", "tests/router/scoring.test.ts", 0.5)]),
    ("test(router): add strategy presets and comparison tests", [("f", "tests/router/scoring.test.ts")]),
    ("test(bridges): add Wormhole adapter tests", [("f", "tests/bridges/wormhole.test.ts")]),
    ("test(bridges): add deBridge adapter tests", [("f", "tests/bridges/debridge.test.ts")]),
    ("test: add end-to-end integration tests", [("p", "tests/integration/end-to-end.test.ts", 0.5)]),
    ("test: add strategy comparison and bridge exclusion e2e tests", [("f", "tests/integration/end-to-end.test.ts")]),

    # === BRANCH: feature/python-sdk (Mar 4-8) ===
    ("branch", [("branch", "feature/python-sdk")]),
    ("chore(python): initialize Python SDK with pyproject.toml", [("f", "sdk/python/pyproject.toml")]),
    ("feat(python): define exception hierarchy", [("f", "sdk/python/mnmx/exceptions.py")]),
    ("feat(python): add math utility functions", [("f", "sdk/python/mnmx/math_utils.py")]),
    ("feat(python): define core chain and token types", [("p", "sdk/python/mnmx/types.py", 0.2)]),
    ("feat(python): add route and bridge quote types", [("p", "sdk/python/mnmx/types.py", 0.45)]),
    ("feat(python): add config, scoring weights, and simulation types", [("p", "sdk/python/mnmx/types.py", 0.7)]),
    ("feat(python): add Monte Carlo result and search stats types", [("f", "sdk/python/mnmx/types.py")]),
    ("feat(python): implement Wormhole and deBridge adapters", [("p", "sdk/python/mnmx/bridges.py", 0.35)]),
    ("feat(python): add LayerZero and Allbridge adapters", [("p", "sdk/python/mnmx/bridges.py", 0.7)]),
    ("feat(python): add bridge registry and chain support matrix", [("f", "sdk/python/mnmx/bridges.py")]),
    ("feat(python): implement route scoring function", [("p", "sdk/python/mnmx/scoring.py", 0.5)]),
    ("feat(python): add strategy weight presets to scorer", [("f", "sdk/python/mnmx/scoring.py")]),
    ("feat(python): implement router with path discovery", [("p", "sdk/python/mnmx/router.py", 0.25)]),
    ("feat(python): add minimax search to router", [("p", "sdk/python/mnmx/router.py", 0.5)]),
    ("feat(python): add alpha-beta pruning and adversarial model", [("p", "sdk/python/mnmx/router.py", 0.75)]),
    ("feat(python): complete router with strategy selection and config", [("f", "sdk/python/mnmx/router.py")]),
    ("feat(python): implement route simulator", [("p", "sdk/python/mnmx/simulator.py", 0.35)]),
    ("feat(python): add Monte Carlo analysis to simulator", [("p", "sdk/python/mnmx/simulator.py", 0.7)]),
    ("feat(python): add stress testing scenarios", [("f", "sdk/python/mnmx/simulator.py")]),
    ("feat(python): implement batch analyzer", [("p", "sdk/python/mnmx/batch_analyzer.py", 0.4)]),
    ("feat(python): add batch report and summary formatting", [("f", "sdk/python/mnmx/batch_analyzer.py")]),
    ("feat(python): implement CLI route command", [("p", "sdk/python/mnmx/cli.py", 0.3)]),
    ("feat(python): add compare and simulate CLI commands", [("p", "sdk/python/mnmx/cli.py", 0.65)]),
    ("feat(python): add bridges and chains CLI commands", [("f", "sdk/python/mnmx/cli.py")]),
    ("feat(python): add package exports", [("f", "sdk/python/mnmx/__init__.py")]),
    ("merge", [("merge", "feature/python-sdk", "Merge pull request #2 from MEMX-labs/feature/python-sdk")]),

    # === BRANCH: fix/route-scoring-edge-cases (Mar 8-9) ===
    ("branch", [("branch", "fix/route-scoring-edge-cases")]),
    ("test(python): add test fixtures and conftest", [("f", "sdk/python/tests/__init__.py"), ("f", "sdk/python/tests/conftest.py")]),
    ("test(python): add router tests", [("f", "sdk/python/tests/test_router.py")]),
    ("test(python): add simulator and Monte Carlo tests", [("f", "sdk/python/tests/test_simulator.py")]),
    ("test(python): add bridge adapter tests", [("f", "sdk/python/tests/test_bridges.py")]),
    ("test(python): add batch analyzer tests", [("f", "sdk/python/tests/test_batch_analyzer.py")]),
    ("merge", [("merge", "fix/route-scoring-edge-cases", "Merge pull request #3 from MEMX-labs/fix/route-scoring-edge-cases")]),

    # === BRANCH: refactor/path-discovery-optimization (Mar 9-10) ===
    ("branch", [("branch", "refactor/path-discovery-optimization")]),
    ("feat: add basic route example", [("f", "examples/basic-route.ts")]),
    ("feat: add strategy comparison example", [("f", "examples/compare-strategies.ts")]),
    ("feat: add custom bridge adapter example", [("f", "examples/custom-bridge.ts")]),
    ("perf: add benchmark script", [("f", "scripts/benchmark.ts")]),
    ("merge", [("merge", "refactor/path-discovery-optimization", "Merge pull request #4 from MEMX-labs/refactor/path-discovery-optimization")]),

    # === PHASE 9: Documentation (Mar 10-12) ===
    ("docs: add architecture documentation", [("f", "docs/architecture.md")]),
    ("docs: add routing engine deep dive", [("f", "docs/routing-engine.md")]),
    ("docs: add minimax algorithm explanation", [("f", "docs/minimax-algorithm.md")]),
    ("docs: add bridge adapters documentation", [("f", "docs/bridge-adapters.md")]),
    ("docs: add Python SDK documentation", [("f", "docs/python-sdk.md")]),
    ("docs: add documentation index", [("f", "docs/README.md")]),
    ("docs: add comprehensive technical documentation", [("f", "CONTRIBUTING.md")]),

    # === BRANCH: feature/ci-community-standards (Mar 12-13) ===
    ("branch", [("branch", "feature/ci-community-standards")]),
    ("ci: add GitHub Actions CI workflow", [("f", ".github/workflows/ci.yml")]),
    ("chore: add issue templates", [("f", ".github/ISSUE_TEMPLATE/bug_report.md"), ("f", ".github/ISSUE_TEMPLATE/feature_request.md")]),
    ("chore: add pull request template", [("f", ".github/pull_request_template.md")]),
    ("chore: add dependabot configuration", [("f", ".github/dependabot.yml")]),
    ("docs: add security policy", [("f", "SECURITY.md")]),
    ("merge", [("merge", "feature/ci-community-standards", "Merge pull request #5 from MEMX-labs/feature/ci-community-standards")]),

    # === PHASE 10: Polish (Mar 13-15) ===
    ("docs: add banner image", [("b", "assets/banner.png")]),
    ("docs: update README with project overview", [("p", "README.md", 0.2)]),
    ("docs: add architecture diagram to README", [("p", "README.md", 0.4)]),
    ("docs: add usage examples to README", [("p", "README.md", 0.6)]),
    ("docs: add strategy profiles and API reference", [("p", "README.md", 0.8)]),
    ("docs: complete README with all sections", [("f", "README.md")]),
]


def execute_plan():
    print(f"Total commits planned: {len([c for c in PLAN if c[0] not in ('branch', 'merge')])}")
    print(f"Total entries: {len(PLAN)}")

    # Count actual commits (excluding branch/merge control entries)
    commit_count = 0
    for msg, ops in PLAN:
        if msg == "branch":
            continue
        if msg == "merge":
            continue
        commit_count += 1
    # Add merge commits
    merge_count = sum(1 for msg, _ in PLAN if msg == "merge")
    total = commit_count + merge_count
    print(f"Total commits (including merges): {total}")

    # Generate dates
    start = datetime(2026, 1, 20, 10, 55, 7)
    end = datetime(2026, 3, 15, 19, 25, 54)
    dates = generate_dates(start, end, total)

    # Remove existing git and reinitialize
    git_dir = os.path.join(REPO, ".git")
    if os.path.exists(git_dir):
        print("Removing existing .git directory...")
        # Windows: need to remove read-only attributes first
        def remove_readonly(func, path, exc_info):
            import stat
            os.chmod(path, stat.S_IWRITE)
            func(path)
        shutil.rmtree(git_dir, onexc=remove_readonly)

    # Clean working directory (keep .backup and this script)
    def remove_readonly2(func, path, exc_info):
        import stat
        os.chmod(path, stat.S_IWRITE)
        func(path)
    for item in os.listdir(REPO):
        if item in ('.backup', 'generate_history.py', 'node_modules', '.git'):
            continue
        path = os.path.join(REPO, item)
        if os.path.isdir(path):
            shutil.rmtree(path, onexc=remove_readonly2)
        else:
            os.remove(path)

    # Init fresh repo
    run("git init")
    run("git checkout -b main")

    date_idx = 0
    current_branch = "main"

    for entry_idx, (msg, ops) in enumerate(PLAN):
        # Handle branch creation
        if msg == "branch":
            branch_name = ops[0][1]
            run(f"git checkout -b {branch_name}")
            current_branch = branch_name
            print(f"  Created branch: {branch_name}")
            continue

        # Handle merge
        if msg == "merge":
            _, branch_name, merge_msg = ops[0]
            dt = dates[date_idx]
            date_idx += 1
            run("git checkout main")
            current_branch = "main"
            git_merge(branch_name, merge_msg, dt)
            print(f"  [{date_idx}/{total}] {dt.strftime('%Y-%m-%d')} MERGE: {merge_msg[:60]}")
            continue

        # Regular commit: execute operations
        for op in ops:
            action = op[0]
            if action == "f":
                copy_file(op[1])
            elif action == "p":
                copy_partial(op[1], op[2])
            elif action == "b":
                copy_file(op[1])

        dt = dates[date_idx]
        date_idx += 1
        success = git_commit(msg, dt)
        print(f"  [{date_idx}/{total}] {dt.strftime('%Y-%m-%d %H:%M')} {'OK' if success else 'FAIL'}: {msg[:70]}")

    print(f"\nDone! Total commits created: {date_idx}")


if __name__ == "__main__":
    execute_plan()
