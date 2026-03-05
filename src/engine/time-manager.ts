/**
 * MNMX Time Manager
 *
 * Allocates search time across iterative deepening depths using a model
 * inspired by chess engine time controls. Adapts allocation based on the
 * "game phase" of the on-chain environment:
 *
 *  - Opening:  many candidate actions, broad search, conservative time use.
 *  - Midgame:  moderate branching, balanced allocation.
 *  - Endgame:  few critical actions, deep search, aggressive time use.
 *
 * Also provides extension logic for unstable positions (where the best
 * move changes between iterations) and single-reply situations (where
 * only one reasonable action exists and search can terminate early).
 */

import type { SearchConfig } from '../types/index.js';

// ── Types ────────────────────────────────────────────────────────────

export type GamePhase = 'opening' | 'midgame' | 'endgame';

export interface TimeAllocation {
  /** Total time budget for this search invocation (ms). */
  readonly totalBudgetMs: number;
  /** Hard deadline -- search must stop by this time (ms since epoch). */
  readonly hardDeadlineMs: number;
  /** Soft target -- aim to finish each iteration within this (ms). */
  readonly softTargetMs: number;
  /** Maximum time allowed for a single depth iteration (ms). */
  readonly maxIterationMs: number;
  /** Time already consumed when this allocation was created (ms). */
  readonly elapsedAtCreation: number;
  /** Whether an extension has been applied. */
  readonly extended: boolean;
  /** Reason for the most recent extension, if any. */
  readonly extensionReason: string | null;
  /** Timestamp of allocation creation (ms since epoch). */
  readonly createdAt: number;
}

export interface DepthTiming {
  readonly depth: number;
  readonly startMs: number;
  readonly endMs: number;
  readonly durationMs: number;
  readonly nodesSearched: number;
}

// ── Phase Coefficients ───────────────────────────────────────────────

/**
 * Fraction of total time to use as the soft target.
 * Opening uses less (saving time for deeper iterations), endgame uses more.
 */
const SOFT_TARGET_FRACTION: Record<GamePhase, number> = {
  opening: 0.35,
  midgame: 0.50,
  endgame: 0.70,
};

/**
 * Maximum fraction of total time any single iteration may consume.
 */
const MAX_ITERATION_FRACTION: Record<GamePhase, number> = {
  opening: 0.25,
  midgame: 0.40,
  endgame: 0.55,
};

/**
 * Extension multiplier applied to the soft target when extending.
 */
const EXTENSION_MULTIPLIER: Record<string, number> = {
  instability: 1.5,
  single_reply: 0.3,
};

// ── Time Manager ─────────────────────────────────────────────────────

export class TimeManager {
  private readonly depthTimings: DepthTiming[] = [];
  private emergencyStopped = false;

  /**
   * Create a time allocation for a search invocation.
   */
  allocate(config: SearchConfig, gamePhase: GamePhase): TimeAllocation {
    const now = performance.now();
    const totalBudget = config.timeLimitMs;

    const softTarget = totalBudget * SOFT_TARGET_FRACTION[gamePhase];
    const maxIteration = totalBudget * MAX_ITERATION_FRACTION[gamePhase];

    return {
      totalBudgetMs: totalBudget,
      hardDeadlineMs: now + totalBudget,
      softTargetMs: softTarget,
      maxIterationMs: maxIteration,
      elapsedAtCreation: 0,
      extended: false,
      extensionReason: null,
      createdAt: now,
    };
  }

  /**
   * Determine whether search should stop at the current point.
   *
   * Returns true if:
   *  1. The hard deadline has been reached, or
   *  2. The elapsed time exceeds the soft target and we are between
   *     iterations (not mid-search), or
   *  3. The predicted time for the next depth exceeds the remaining budget.
   *  4. An emergency stop has been triggered.
   */
  shouldStop(elapsed: number, allocation: TimeAllocation): boolean {
    if (this.emergencyStopped) return true;

    // Hard deadline
    if (elapsed >= allocation.totalBudgetMs) return true;

    // Soft target exceeded
    if (elapsed >= allocation.softTargetMs) {
      // Predict next iteration duration using exponential growth model
      const predicted = this.predictNextIterationMs();
      const remaining = allocation.totalBudgetMs - elapsed;
