use criterion::{black_box, criterion_group, criterion_main, Criterion};
use mnmx_engine::bridge::build_mock_registry;
use mnmx_engine::minimax::MinimaxSearcher;
use mnmx_engine::path_discovery::PathDiscovery;
use mnmx_engine::scoring::RouteScorer;
use mnmx_engine::types::*;

fn eth_usdc() -> Token {
    Token::new("USDC", Chain::Ethereum, 6, "0xA0b86991")
}

fn arb_usdc() -> Token {
    Token::new("USDC", Chain::Arbitrum, 6, "0xaf88d065")
}

fn base_usdc() -> Token {
    Token::new("USDC", Chain::Base, 6, "0x833589fC")
}

fn bench_path_discovery(c: &mut Criterion) {
    let registry = build_mock_registry();

    c.bench_function("path_discovery_2hop", |b| {
        b.iter(|| {
            let pd = PathDiscovery::new(&registry, 2);
            let paths = pd.discover_paths(
                Chain::Ethereum,
                &eth_usdc(),
                Chain::Base,
                &base_usdc(),
            );
            black_box(paths);
        });
    });

    c.bench_function("path_discovery_3hop", |b| {
        b.iter(|| {
            let pd = PathDiscovery::new(&registry, 3);
            let paths = pd.discover_paths(
                Chain::Ethereum,
                &eth_usdc(),
                Chain::Base,
                &base_usdc(),
            );
            black_box(paths);
        });
    });
}

fn bench_minimax_search(c: &mut Criterion) {
    let registry = build_mock_registry();

    c.bench_function("minimax_1hop", |b| {
        b.iter(|| {
            let config = RouterConfig {
                max_hops: 1,
                ..RouterConfig::default()
            };
            let mut searcher = MinimaxSearcher::new(config);
            let result = searcher.search(
                &registry,
                Chain::Ethereum,
                &eth_usdc(),
                Chain::Arbitrum,
                &arb_usdc(),
                black_box(10000.0),
            );
            black_box(result);
        });
    });

    c.bench_function("minimax_2hop", |b| {
        b.iter(|| {
            let config = RouterConfig {
                max_hops: 2,
                ..RouterConfig::default()
            };
            let mut searcher = MinimaxSearcher::new(config);
            let result = searcher.search(
                &registry,
                Chain::Ethereum,
                &eth_usdc(),
                Chain::Base,
                &base_usdc(),
                black_box(10000.0),
            );
            black_box(result);
        });
    });
}

fn bench_route_scoring(c: &mut Criterion) {
    let scorer = RouteScorer::with_strategy(Strategy::Minimax);

    // Build a sample route
    let mut route = Route::new();
    route.hops.push(RouteHop {
        from_chain: Chain::Ethereum,
        to_chain: Chain::Arbitrum,
        from_token: eth_usdc(),
        to_token: arb_usdc(),
        bridge: "LayerZero".to_string(),
        input_amount: 10000.0,
        output_amount: 9980.0,
        fee: 20.0,
        estimated_time: 60,
    });
    route.expected_output = 9980.0;
    route.total_fees = 20.0;
    route.estimated_time = 60;

    c.bench_function("score_single_hop_route", |b| {
        b.iter(|| {
            let score = scorer.score_route(black_box(&route));
            black_box(score);
        });
    });

    // Multi-hop route
    let mut multi_route = route.clone();
    multi_route.hops.push(RouteHop {
        from_chain: Chain::Arbitrum,
        to_chain: Chain::Base,
        from_token: arb_usdc(),
        to_token: base_usdc(),
        bridge: "LayerZero".to_string(),
        input_amount: 9980.0,
        output_amount: 9960.0,
        fee: 20.0,
        estimated_time: 60,
    });
    multi_route.expected_output = 9960.0;
    multi_route.total_fees = 40.0;
    multi_route.estimated_time = 120;

    c.bench_function("score_multi_hop_route", |b| {
        b.iter(|| {
            let score = scorer.score_route(black_box(&multi_route));
            black_box(score);
        });
    });
}

criterion_group!(
    benches,
    bench_path_discovery,
    bench_minimax_search,
    bench_route_scoring
);
criterion_main!(benches);
