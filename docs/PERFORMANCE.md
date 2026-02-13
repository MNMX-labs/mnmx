# Performance Guide

## Search Optimization

The minimax engine uses several techniques to search efficiently:

### Alpha-Beta Pruning
Eliminates branches that cannot affect the result. Typically reduces
the search space by 90%+ compared to naive minimax.

### Transposition Table
Caches evaluated positions to avoid redundant computation. Most
effective when multiple paths lead to the same intermediate state.

### Move Ordering
Evaluates the most promising routes first, maximizing pruning
efficiency. Uses killer move heuristic and history table.

### Iterative Deepening
Searches progressively deeper, ensuring a valid result is always
available even if the search is interrupted by timeout.

## Benchmarks

| Operation | Typical Time | Notes |
|-----------|-------------|-------|
| Path discovery | <1ms | 8 chains, 4 bridges |
| Minimax search (depth 3) | 1-5ms | With alpha-beta pruning |
| Minimax search (depth 5) | 5-20ms | With transposition table |
| Full route scoring | <0.1ms | Per route |
| End-to-end routing | 5-30ms | Discovery + search + scoring |

## Configuration Tips

- Set `maxHops` to 2 for fast results, 3 for optimal results
- Use `fastest` strategy when latency matters more than cost
- Reduce `timeout` for real-time applications
- Increase transposition table size for deep searches
