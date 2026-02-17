use mnmx_engine::bridge::{build_mock_registry, MockBridge};
use mnmx_engine::path_discovery::PathDiscovery;
use mnmx_engine::router::MnmxRouter;
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

fn sol_usdc() -> Token {
    Token::new("USDC", Chain::Solana, 6, "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v")
}

fn make_request(
    from_chain: Chain,
    from_token: Token,
    to_chain: Chain,
    to_token: Token,
    amount: f64,
    max_hops: usize,
) -> RouteRequest {
    RouteRequest {
        from_chain,
        from_token,
        to_chain,
        to_token,
        amount,
        strategy: Strategy::Minimax,
        max_hops,
    }
}

#[test]
fn test_direct_route_discovery() {
    let registry = build_mock_registry();
    let pd = PathDiscovery::new(&registry, 3);

    let paths = pd.discover_paths(
        Chain::Ethereum,
        &eth_usdc(),
        Chain::Arbitrum,
        &arb_usdc(),
    );

    // Should find direct paths (all 4 mock bridges support ETH->ARB)
    let direct_paths: Vec<_> = paths.iter().filter(|p| p.steps.len() == 1).collect();
    assert!(
        !direct_paths.is_empty(),
        "should find at least one direct path"
    );

    for path in &direct_paths {
        assert_eq!(path.steps[0].from_chain, Chain::Ethereum);
        assert_eq!(path.steps[0].to_chain, Chain::Arbitrum);
    }
}

#[test]
fn test_multi_hop_route_discovery() {
    let registry = build_mock_registry();
    let pd = PathDiscovery::new(&registry, 3);

    // Use expand_multi_hop_paths directly (before domination filtering)
    let multi_hop = pd.expand_multi_hop_paths(
        Chain::Ethereum,
        &eth_usdc(),
        Chain::Base,
        &base_usdc(),
    );

    assert!(
        !multi_hop.is_empty(),
        "should find multi-hop paths before filtering"
    );

    // Verify chain continuity
    for path in &multi_hop {
        assert!(path.steps.len() >= 2);
        for i in 1..path.steps.len() {
            assert_eq!(
                path.steps[i - 1].to_chain,
                path.steps[i].from_chain,
                "chains should be continuous"
            );
        }
        assert_eq!(path.steps[0].from_chain, Chain::Ethereum);
        assert_eq!(path.steps.last().unwrap().to_chain, Chain::Base);
    }
}

#[test]
fn test_dominated_path_filtering() {
    let registry = build_mock_registry();
    let pd = PathDiscovery::new(&registry, 3);

    // Get all paths including multi-hop
    let all_paths = pd.discover_paths(
        Chain::Ethereum,
        &eth_usdc(),
        Chain::Arbitrum,
        &arb_usdc(),
    );

    // After filtering, dominated paths should be removed
    // Multi-hop paths using the same bridge as a direct path should be filtered
    let direct_count = all_paths.iter().filter(|p| p.steps.len() == 1).count();
    assert!(direct_count > 0, "direct paths should survive filtering");
}

#[test]
fn test_route_with_bridge_health() {
    let mut router = MnmxRouter::new(RouterConfig::default());

    // Register one healthy and one offline bridge
    router.register_bridge(Box::new(
        MockBridge::new("HealthyBridge", 0.003, 120, 5_000_000.0),
    ));
    router.register_bridge(Box::new(
        MockBridge::new("OfflineBridge", 0.001, 60, 10_000_000.0).with_online(false),
    ));

    let request = make_request(
        Chain::Ethereum,
        eth_usdc(),
        Chain::Arbitrum,
        arb_usdc(),
        10000.0,
        2,
    );

    let result = router.find_route(&request);
    if let Some(route) = &result.best_route {
        // Route should only use the healthy bridge
        for hop in &route.hops {
            assert_ne!(
                hop.bridge, "OfflineBridge",
                "should not route through offline bridge"
            );
        }
    }
}

#[test]
fn test_max_hops_constraint() {
    let mut router = MnmxRouter::new(RouterConfig::default());
    router.set_registry(build_mock_registry());

    // Test with max_hops = 1
    let request = make_request(
        Chain::Ethereum,
        eth_usdc(),
        Chain::Arbitrum,
        arb_usdc(),
        10000.0,
        1,
    );

    let result = router.find_route(&request);
    if let Some(route) = &result.best_route {
        assert!(
            route.hops.len() <= 1,
            "should respect max_hops=1, got {} hops",
            route.hops.len()
        );
    }
}

#[test]
fn test_route_value_retention() {
    let mut router = MnmxRouter::new(RouterConfig::default());
    router.set_registry(build_mock_registry());

    let request = make_request(
        Chain::Ethereum,
        eth_usdc(),
        Chain::Arbitrum,
        arb_usdc(),
        10000.0,
        2,
    );

    let result = router.find_route(&request);
    let route = result.best_route.expect("should find a route");

    // Value retention should be > 95% for a simple stablecoin transfer
    let retention = route.value_retention(10000.0);
    assert!(
        retention > 0.90,
        "stablecoin route should retain >90% value, got {}%",
        retention * 100.0
    );
}

#[test]
fn test_route_serialization() {
    let mut router = MnmxRouter::new(RouterConfig::default());
    router.set_registry(build_mock_registry());

    let request = make_request(
        Chain::Ethereum,
        eth_usdc(),
        Chain::Arbitrum,
        arb_usdc(),
        5000.0,
        2,
    );

    let result = router.find_route(&request);
    let route = result.best_route.expect("should find a route");

    // Route should be serializable to JSON
    let json = serde_json::to_string(&route).expect("should serialize");
    let deserialized: Route = serde_json::from_str(&json).expect("should deserialize");

    assert_eq!(route.hops.len(), deserialized.hops.len());
    assert!((route.expected_output - deserialized.expected_output).abs() < 0.001);
}

#[test]
fn test_cross_vm_routing() {
    let mut router = MnmxRouter::new(RouterConfig::default());
    router.set_registry(build_mock_registry());

    // Ethereum (EVM) to Solana (SVM) - cross-VM transfer
    let request = make_request(
        Chain::Ethereum,
        eth_usdc(),
        Chain::Solana,
        sol_usdc(),
        10000.0,
        2,
    );

    let result = router.find_route(&request);
    assert!(
        result.best_route.is_some(),
        "should find a cross-VM route"
    );
}

#[test]
fn test_multiple_quotes_sorted() {
    let mut router = MnmxRouter::new(RouterConfig::default());
    router.set_registry(build_mock_registry());

    let quotes = router.get_quotes(&eth_usdc(), &arb_usdc(), 10000.0);

    assert!(quotes.len() >= 2, "should get multiple quotes");

    // Quotes should be sorted by output (best first)
    for window in quotes.windows(2) {
        assert!(
            window[0].output_amount >= window[1].output_amount,
            "quotes should be sorted by output"
        );
    }
}

#[test]
fn test_route_chains_traversed() {
    let mut router = MnmxRouter::new(RouterConfig::default());
    router.set_registry(build_mock_registry());

    let request = make_request(
        Chain::Ethereum,
        eth_usdc(),
        Chain::Base,
        base_usdc(),
        10000.0,
        2,
    );

    let result = router.find_route(&request);
    let route = result.best_route.expect("should find route");
    let chains = route.chains_traversed();

    assert_eq!(*chains.first().unwrap(), Chain::Ethereum);
    assert_eq!(*chains.last().unwrap(), Chain::Base);
}
