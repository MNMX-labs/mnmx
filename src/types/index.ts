/**
 * MNMX Core Type Definitions
 *
 * Canonical types for the minimax execution engine, covering game tree
 * representation, on-chain state modeling, MEV threat classification,
 * and search/evaluation configuration.
 */

// ── Player Designation ──────────────────────────────────────────────

/** The two adversarial roles in the game tree. */
export type Player = 'agent' | 'adversary';

// ── Action Taxonomy ─────────────────────────────────────────────────

/** Exhaustive set of on-chain action categories the engine can plan. */
export type ActionKind =
  | 'swap'
  | 'transfer'
  | 'stake'
  | 'unstake'
  | 'liquidate'
  | 'provide_liquidity'
  | 'remove_liquidity'
  | 'borrow'
  | 'repay';

/** An atomic on-chain action the agent may execute. */
export interface ExecutionAction {
  readonly kind: ActionKind;
  readonly tokenMintIn: string;
  readonly tokenMintOut: string;
  readonly amount: bigint;
  readonly slippageBps: number;
  readonly pool: string;
  readonly priority: number;
  readonly label: string;
}

// ── Game Tree ───────────────────────────────────────────────────────

/** A single vertex in the minimax game tree. */
export interface GameNode {
  readonly action: ExecutionAction | null;
  readonly stateHash: string;
  children: GameNode[];
  score: number;
  readonly depth: number;
  isTerminal: boolean;
  readonly player: Player;
}

// ── Evaluation ──────────────────────────────────────────────────────

/** Granular breakdown of a position evaluation. */
export interface EvaluationBreakdown {
  gasCost: number;
  slippageImpact: number;
  mevExposure: number;
  profitPotential: number;
}

/** Composite result of evaluating a (state, action) pair. */
export interface EvaluationResult {
  score: number;
  breakdown: EvaluationBreakdown;
  confidence: number;
}

/** Weights applied to each evaluation component in the linear combination. */
export interface EvaluationWeights {
  gasCost: number;
  slippageImpact: number;
  mevExposure: number;
  profitPotential: number;
}

// ── Search Configuration ────────────────────────────────────────────

/** Parameters governing the minimax search behaviour. */
export interface SearchConfig {
  readonly maxDepth: number;
  readonly alphaBetaPruning: boolean;
  readonly timeLimitMs: number;
  readonly evaluationWeights: EvaluationWeights;
  readonly maxTranspositionEntries: number;
}
