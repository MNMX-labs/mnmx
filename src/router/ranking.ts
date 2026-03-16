// ─────────────────────────────────────────────────────────────
// Route Ranking Comparator
// Simplified ranking logic extracted from minimax engine
// ─────────────────────────────────────────────────────────────

import type { Strategy } from '../types/index.js';

export interface RankedRoute {
  id: string;
  minimaxScore: number;
  normalScore: number;
  worstCaseOutput: number;
  expectedOutput: number;
  fees: number;
  estimatedTime: number;
}

/**
 * Compare two routes based on strategy.
 * Returns negative if a should rank higher, positive if b should.
 */
export function compareRoutes(a: RankedRoute, b: RankedRoute, strategy: Strategy): number {
  switch (strategy) {
    case 'minimax':
      // Primary: worst-case output (higher is better)
      // Tiebreak: minimax score
      if (a.worstCaseOutput !== b.worstCaseOutput) {
        return b.worstCaseOutput - a.worstCaseOutput;
      }
      return b.minimaxScore - a.minimaxScore;

    case 'fastest':
      // Primary: estimated time (lower is better)
      // Tiebreak: expected output
      if (a.estimatedTime !== b.estimatedTime) {
        return a.estimatedTime - b.estimatedTime;
      }
      return b.expectedOutput - a.expectedOutput;

    case 'cheapest':
      // Primary: fees (lower is better)
      // Tiebreak: expected output
      if (a.fees !== b.fees) {
        return a.fees - b.fees;
      }
      return b.expectedOutput - a.expectedOutput;

    case 'safest':
      // Same as minimax but with heavier reliability weight
      return b.minimaxScore - a.minimaxScore;

    default:
      return b.minimaxScore - a.minimaxScore;
  }
}

/**
 * Rank an array of routes and assign rank numbers.
 */
export function rankRoutes<T extends RankedRoute>(routes: T[], strategy: Strategy): (T & { rank: number })[] {
  const sorted = [...routes].sort((a, b) => compareRoutes(a, b, strategy));
  return sorted.map((r, i) => ({ ...r, rank: i + 1 }));
}
