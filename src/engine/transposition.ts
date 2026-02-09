/**
 * MNMX Transposition Table
 *
 * Caches previously evaluated game-tree positions so that when the
 * same on-chain state is reached via a different move order we can
 * skip re-evaluation.  Uses depth-preferred replacement with an aging
 * mechanism to evict stale entries when the table is at capacity.
 */

import type { ExecutionAction } from '../types/index.js';

// ── Entry Types ─────────────────────────────────────────────────────

export type BoundFlag = 'exact' | 'lower' | 'upper';

export interface TranspositionEntry {
  hash: string;
  depth: number;
  score: number;
  flag: BoundFlag;
  bestAction?: ExecutionAction;
  age: number;
}

export interface TableStats {
  entries: number;
  hits: number;
  misses: number;
  hitRate: number;
  overwrites: number;
}

export interface LookupResult {
  score: number;
  found: boolean;
  bestAction?: ExecutionAction;
}

// ── Transposition Table ─────────────────────────────────────────────

export class TranspositionTable {
  private readonly entries = new Map<string, TranspositionEntry>();
  private readonly maxEntries: number;
  private currentAge = 0;
  private hits = 0;
  private misses = 0;
  private overwrites = 0;
