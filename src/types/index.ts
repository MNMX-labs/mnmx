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
