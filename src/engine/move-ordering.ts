/**
 * MNMX Move Ordering
 *
 * Dramatically improves alpha-beta pruning efficiency by evaluating the
 * most promising actions first.  Combines three heuristics drawn from
 * game-engine research and adapted to on-chain DeFi context:
 *
 *  1. Killer moves   – refutation moves that caused a beta cutoff at the
 *                      same depth in a sibling branch.
 *  2. History table  – actions that have historically produced high scores
 *                      are tried earlier regardless of depth.
 *  3. MVV-LVA        – Most Valuable Victim / Least Valuable Aggressor,
 *                      re-interpreted for DeFi as "highest expected value
 *                      per unit of cost (gas + slippage)".
 */

import type { ExecutionAction, OnChainState } from '../types/index.js';

// ── Killer-Move Storage ─────────────────────────────────────────────

const MAX_KILLER_SLOTS = 2; // two killer slots per depth level

function actionKey(a: ExecutionAction): string {
  return `${a.kind}:${a.pool}:${a.tokenMintIn}:${a.tokenMintOut}:${a.amount}`;
}

// ── Class ───────────────────────────────────────────────────────────

export class MoveOrderer {
  /** killerMoves[depth] holds up to MAX_KILLER_SLOTS action keys. */
  private readonly killerMoves: Map<number, string[]> = new Map();

  /** Cumulative score for every action key that ever caused an improvement. */
  private readonly historyScores: Map<string, number> = new Map();

  // ── Public API ──────────────────────────────────────────────────

  /**
   * Return `actions` sorted so that the most promising candidates
   * appear first.  Does not mutate the input array.
   */
  orderMoves(
    actions: ReadonlyArray<ExecutionAction>,
    state: OnChainState,
    depth: number = 0,
  ): ExecutionAction[] {
    // Score each action with a composite ordering value
    const scored = actions.map((action) => ({
      action,
      orderScore: this.computeOrderScore(action, state, depth),
    }));
