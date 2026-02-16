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
