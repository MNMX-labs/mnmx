use criterion::{black_box, criterion_group, criterion_main, Criterion};
use std::collections::HashMap;

use mnmx_engine::*;

fn make_bench_state() -> OnChainState {
    let mut balances = HashMap::new();
    balances.insert("SOL".to_string(), 5_000_000);
    balances.insert("USDC".to_string(), 25_000_000);
    balances.insert("RAY".to_string(), 1_000_000);

    OnChainState {
        token_balances: balances,
        pool_states: vec![
            PoolState::new("pool_sol_usdc", 100_000_000, 500_000_000, 30, "SOL", "USDC"),
            PoolState::new("pool_ray_usdc", 50_000_000, 100_000_000, 25, "RAY", "USDC"),
        ],
        pending_transactions: vec![
            PendingTx::new("sig1", "user1", "pool_sol_usdc", 200_000, 100, 5000),
            PendingTx::new("sig2", "MEVbot", "pool_sol_usdc", 500_000, 100, 50_000),
        ],
        slot: 300,
        block_time: 1700000000,
    }
}

fn make_bench_actions() -> Vec<ExecutionAction> {
    vec![
        ExecutionAction::new(ActionKind::Swap, "SOL", 500_000, "USDC", 50, "pool_sol_usdc", 5000),
        ExecutionAction::new(ActionKind::Swap, "SOL", 200_000, "USDC", 30, "pool_sol_usdc", 3000),
        ExecutionAction::new(ActionKind::Swap, "USDC", 2_000_000, "SOL", 100, "pool_sol_usdc", 8000),
        ExecutionAction::new(ActionKind::Swap, "RAY", 300_000, "USDC", 50, "pool_ray_usdc", 5000),
    ]
}

fn bench_minimax_depth_3(c: &mut Criterion) {
    let state = make_bench_state();
    let actions = make_bench_actions();

    c.bench_function("minimax_depth_3", |b| {
        b.iter(|| {
            let config = SearchConfig {
                max_depth: 3,
                alpha_beta_enabled: true,
                time_limit_ms: 30_000,
                transposition_enabled: true,
                move_ordering_enabled: true,
                ..SearchConfig::default()
            };
            let mut engine = MinimaxEngine::new(config);
            let plan = engine.search(black_box(&state), black_box(&actions));
            black_box(plan);
        });
    });
}
