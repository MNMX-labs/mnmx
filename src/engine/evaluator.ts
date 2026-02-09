/**
 * MNMX Position Evaluator
 *
 * Assigns a scalar score to a (state, action) pair by analysing four
 * orthogonal dimensions of execution quality:
 *
 *  - Gas cost         (compute units + priority fee overhead)
 *  - Slippage impact  (market-impact loss relative to midpoint price)
 *  - MEV exposure     (probability-weighted cost of adversarial extraction)
 *  - Profit potential  (net expected value after all costs)
 *
 * Each dimension produces a normalised sub-score in [0, 1] which is
 * combined via a configurable weight vector into the final evaluation.
 */

import type {
  EvaluationResult,
  EvaluationWeights,
  ExecutionAction,
  OnChainState,
  PoolState,
  SearchConfig,
} from '../types/index.js';
import {
  calculateSlippage,
  constantProductSwap,
  estimatePriceImpact,
} from '../utils/math.js';

// ── Constants ───────────────────────────────────────────────────────

/** Baseline compute-unit cost for a simple Solana instruction. */
const BASE_COMPUTE_UNITS = 200_000;

/** Extra CU overhead per action kind (rough estimates). */
const CU_OVERHEADS: Record<string, number> = {
  swap: 150_000,
  transfer: 50_000,
  stake: 120_000,
  unstake: 120_000,
  liquidate: 300_000,
  provide_liquidity: 200_000,
  remove_liquidity: 180_000,
  borrow: 250_000,
  repay: 220_000,
};

/** Maximum compute budget we consider "normal". */
const MAX_ACCEPTABLE_CU = 1_400_000;

/** Lamports per compute unit at typical priority. */
const MICRO_LAMPORTS_PER_CU = 1_000;

/** Slots before state data is considered stale. */
const STALENESS_THRESHOLD_SLOTS = 5;

// ── Evaluator ───────────────────────────────────────────────────────

export class PositionEvaluator {
  private readonly weights: EvaluationWeights;

  constructor(config: SearchConfig) {
    this.weights = config.evaluationWeights;
  }

  /**
   * Evaluate a proposed action given the current on-chain state.
   * Returns a composite score, a per-dimension breakdown, and a
   * confidence metric.
   */
  evaluate(state: OnChainState, action: ExecutionAction): EvaluationResult {
    const gasScore = this.evaluateGasCost(action);
    const slippageScore = this.evaluateSlippage(state, action);
    const mevScore = this.evaluateMevExposure(state, action);
    const profitScore = this.evaluateProfit(state, action);

    // Weighted linear combination – each sub-score is in [0, 1]
    const composite =
      gasScore * this.weights.gasCost +
      slippageScore * this.weights.slippageImpact +
      mevScore * this.weights.mevExposure +
      profitScore * this.weights.profitPotential;

    const confidence = this.computeConfidence(state, action);

    return {
      score: composite * confidence,
      breakdown: {
        gasCost: gasScore,
        slippageImpact: slippageScore,
        mevExposure: mevScore,
        profitPotential: profitScore,
      },
      confidence,
    };
  }

  // ── Gas Cost ────────────────────────────────────────────────────
