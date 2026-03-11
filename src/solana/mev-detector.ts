/**
 * MNMX MEV Detector
 *
 * Analyses pending transactions and pool state to identify probable
 * MEV threats against a proposed on-chain action.  Covers sandwich
 * attacks, frontrunning, backrunning, and JIT liquidity provision.
 */

import { Connection, PublicKey } from '@solana/web3.js';
import type {
  ExecutionAction,
  MevThreat,
  PendingTx,
  PoolState,
} from '../types/index.js';

// ── Known MEV Bot Patterns ──────────────────────────────────────────

/**
 * Heuristic signatures of known MEV bot programs and wallets.
 * In production these would be maintained via an on-chain registry or
 * external threat-intelligence feed.
 */
const KNOWN_MEV_PROGRAM_IDS = new Set([
  'JUP6LkbZbjS1jKKwapdHNy74zcZ3tLUZoi5QNyVTaV4',  // Jupiter (potential arb relay)
  'whirLbMiicVdio4qvUfM5KAg6Ct8VwpYzGff3uctyCc',  // Orca Whirlpool
]);

/** Wallets historically associated with sandwich bots (illustrative). */
const SUSPECTED_SANDWICH_WALLETS = new Set([
  'SandwichBot1111111111111111111111111111111',
  'MEVBot111111111111111111111111111111111111',
]);

/** Minimum trade-to-reserve ratio that triggers threat analysis. */
const MIN_THREAT_RATIO = 0.0005;

/** Trade ratio above which sandwich probability is near-certain. */
const HIGH_RISK_RATIO = 0.05;

// ── MEV Detector ────────────────────────────────────────────────────

export class MevDetector {
  private readonly connection: Connection;

  constructor(connection: Connection) {
    this.connection = connection;
  }

  /**
   * Run all threat detectors against a proposed action and return
   * the union of identified threats, sorted by estimated cost descending.
   */
  detectThreats(
    action: ExecutionAction,
    recentTxs: PendingTx[],
    poolState?: PoolState,
  ): MevThreat[] {
    const threats: MevThreat[] = [];

    const sandwich = this.analyzeSandwichRisk(action, recentTxs, poolState);
    if (sandwich) threats.push(sandwich);

    const frontrun = this.analyzeFrontrunRisk(action, recentTxs, poolState);
    if (frontrun) threats.push(frontrun);

    const backrun = this.analyzeBackrunRisk(action, recentTxs, poolState);
    if (backrun) threats.push(backrun);

    if (poolState) {
      const jit = this.analyzeJitRisk(action, poolState);
      if (jit) threats.push(jit);
    }

    // Sort by expected cost (probability * estimated cost) descending
    threats.sort((a, b) => {
      const costA = Number(a.estimatedCost) * a.probability;
      const costB = Number(b.estimatedCost) * b.probability;
      return costB - costA;
    });

    return threats;
  }

  /**
   * Analyse the risk of a sandwich attack.
   *
   * A sandwich wraps the victim's swap between a frontleg (buy) and
   * backleg (sell), profiting from the price impact the victim causes.
   * Risk factors:
   *  - Large trade relative to pool reserves
   *  - High slippage tolerance (gives the attacker room)
   *  - Presence of known sandwich bot TXs in recent history
   */
  analyzeSandwichRisk(
    action: ExecutionAction,
    pendingTxs: PendingTx[],
    poolState?: PoolState,
  ): MevThreat | null {
    if (action.kind !== 'swap') return null;

    const tradeRatio = poolState
      ? this.computeTradeRatio(action.amount, poolState)
      : 0;

    if (tradeRatio < MIN_THREAT_RATIO && !this.hasSuspectedBotActivity(pendingTxs)) {
      return null;
    }

    // Probability model: logistic function of trade ratio and slippage
    const ratioProbability = this.logisticProbability(tradeRatio, 0.01, 200);
    const slippageProbability = this.logisticProbability(
      action.slippageBps / 10_000,
      0.005,
      400,
    );
    const botPresenceBoost = this.hasSuspectedBotActivity(pendingTxs) ? 0.15 : 0;

    const probability = Math.min(
      ratioProbability * 0.5 + slippageProbability * 0.35 + botPresenceBoost,
      0.95,
    );

    // Cost estimate: proportional to trade ratio squared (quadratic impact)
    const estimatedCost = this.estimateSandwichCost(action.amount, tradeRatio);

    return {
      kind: 'sandwich',
      probability,
      estimatedCost,
      sourceAddress: this.identifyLikelyBot(pendingTxs, 'sandwich'),
      relatedPool: action.pool,
      description: `Sandwich attack risk: ${(probability * 100).toFixed(1)}% probability, trade/reserve ratio ${(tradeRatio * 100).toFixed(3)}%`,
    };
  }

  /**
   * Analyse the risk of a pure frontrun.
   *
   * A frontrunner submits a similar trade ahead of the victim to
   * benefit from the price movement. Less common than sandwiches on
   * Solana due to deterministic ordering, but possible via Jito bundles.
   */
  analyzeFrontrunRisk(
    action: ExecutionAction,
    pendingTxs: PendingTx[],
    poolState?: PoolState,
  ): MevThreat | null {
    if (!['swap', 'liquidate'].includes(action.kind)) return null;

    const tradeRatio = poolState
      ? this.computeTradeRatio(action.amount, poolState)
      : 0;

    // Look for pending TXs targeting the same pool
    const competingTxCount = pendingTxs.filter((tx) =>
      this.isTargetingPool(tx, action.pool),
    ).length;

    if (tradeRatio < MIN_THREAT_RATIO && competingTxCount === 0) return null;

    const congestionFactor = Math.min(competingTxCount / 10, 1);
    const probability = Math.min(
      this.logisticProbability(tradeRatio, 0.02, 150) * 0.6 +
        congestionFactor * 0.4,
      0.8,
    );

    const estimatedCost = BigInt(
      Math.floor(Number(action.amount) * tradeRatio * 0.2),
    );

    return {
      kind: 'frontrun',
      probability,
      estimatedCost,
      sourceAddress: this.identifyLikelyBot(pendingTxs, 'frontrun'),
      relatedPool: action.pool,
      description: `Frontrun risk: ${competingTxCount} competing txs targeting same pool`,
    };
  }

  /**
   * Analyse the risk of JIT (Just-In-Time) liquidity provision.
   *
   * A JIT provider adds concentrated liquidity in the tick range of
   * the victim's swap, captures the swap fees, then removes liquidity
   * in the same block.  This reduces effective output for the victim.
   */
  analyzeJitRisk(
    action: ExecutionAction,
    poolState: PoolState,
  ): MevThreat | null {
    if (action.kind !== 'swap') return null;

    // JIT is only relevant for concentrated-liquidity pools
    if (!poolState.tickSpacing) return null;

    const tradeRatio = this.computeTradeRatio(action.amount, poolState);
    if (tradeRatio < 0.005) return null;

    // JIT probability increases with trade size and fee rate
    const feeFactor = poolState.feeBps / 100; // higher fees = more attractive for JIT
    const probability = Math.min(
      this.logisticProbability(tradeRatio, 0.01, 100) * 0.7 +
        feeFactor * 0.1,
      0.6,
    );

    const estimatedCost = BigInt(
      Math.floor(Number(action.amount) * (poolState.feeBps / 10_000) * 0.5),
    );

    return {
      kind: 'jit',
      probability,
      estimatedCost,
      sourceAddress: 'JITProvider1111111111111111111111111111111',
      relatedPool: action.pool,
      description: `JIT liquidity risk on CLMM pool with ${poolState.feeBps}bps fee`,
    };
  }

  /**
   * Estimate the absolute cost of an MEV threat in token units.
   */
  estimateMevCost(threat: MevThreat, actionAmount: bigint): bigint {
    return BigInt(
      Math.floor(Number(actionAmount) * threat.probability * Number(threat.estimatedCost) / Number(actionAmount || 1n)),
    );
  }

  // ── Private ─────────────────────────────────────────────────────

  private analyzeBackrunRisk(
    action: ExecutionAction,
    pendingTxs: PendingTx[],
    poolState?: PoolState,
  ): MevThreat | null {
    if (action.kind !== 'swap') return null;

    const tradeRatio = poolState
      ? this.computeTradeRatio(action.amount, poolState)
      : 0;

    if (tradeRatio < 0.005) return null;

    const probability = Math.min(
      this.logisticProbability(tradeRatio, 0.02, 120) * 0.8,
      0.5,
    );

    const estimatedCost = BigInt(
      Math.floor(Number(action.amount) * tradeRatio * 0.1),
    );

    return {
      kind: 'backrun',
      probability,
      estimatedCost,
      sourceAddress: this.identifyLikelyBot(pendingTxs, 'backrun'),
      relatedPool: action.pool,
      description: `Backrun arbitrage risk after large swap (ratio ${(tradeRatio * 100).toFixed(3)}%)`,
    };
  }

  private computeTradeRatio(amount: bigint, pool: PoolState): number {
    const totalReserves = pool.reserveA + pool.reserveB;
    if (totalReserves === 0n) return 0;
    return Number(amount) / Number(totalReserves);
  }

  /**
   * Logistic function mapping a value to a probability in (0, 1).
   * `midpoint` is the value at which probability = 0.5.
   * `steepness` controls how sharply probability transitions.
   */
  private logisticProbability(
    value: number,
    midpoint: number,
    steepness: number,
  ): number {
    return 1 / (1 + Math.exp(-steepness * (value - midpoint)));
  }

  private estimateSandwichCost(amount: bigint, tradeRatio: number): bigint {
    // Quadratic cost model: cost = amount * ratio^2 * scaling_factor
    const scalingFactor = 5;
    const cost = Number(amount) * tradeRatio * tradeRatio * scalingFactor;
    return BigInt(Math.floor(Math.max(cost, 1)));
  }

  private hasSuspectedBotActivity(pendingTxs: PendingTx[]): boolean {
    return pendingTxs.some(
      (tx) =>
        SUSPECTED_SANDWICH_WALLETS.has(tx.fromAddress) ||
        KNOWN_MEV_PROGRAM_IDS.has(tx.programId),
    );
  }

  private isTargetingPool(tx: PendingTx, pool: string): boolean {
    return tx.toAddress === pool || tx.programId === pool;
  }

  private identifyLikelyBot(
    pendingTxs: PendingTx[],
    _threatKind: string,
  ): string {
    const botTx = pendingTxs.find(
      (tx) =>
        SUSPECTED_SANDWICH_WALLETS.has(tx.fromAddress) ||
        KNOWN_MEV_PROGRAM_IDS.has(tx.programId),
    );
    return botTx?.fromAddress ?? 'UnknownBot11111111111111111111111111111111';
  }
}
