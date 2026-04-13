# MNMX Engine (Rust)

Core search engine for cross-chain route optimization.

## Components

| Module | Purpose |
|--------|---------|
| `search.rs` | Minimax search with alpha-beta pruning |
| `scoring.rs` | 5-dimension route evaluation |
| `adversarial.rs` | Worst-case scenario generator |
| `table.rs` | Transposition table (Zobrist hashing) |

## Performance

| Metric | Value |
|--------|-------|
| Candidate paths | 3,000+ per transfer |
| After pruning | 200-500 evaluated |
| Search latency | <10ms |

## Build

```bash
cd engine
cargo check
cargo test
```
