/**
 * MNMX Game Tree Builder
 *
 * Constructs the adversarial game tree that the minimax engine searches.
 * Each level alternates between:
 *
 *  - Agent moves:      the on-chain actions we can execute
 *  - Adversary moves:  MEV bots' probable responses (sandwiches, frontruns, …)
 *
 * The builder also provides state-simulation methods that produce new
 * OnChainState snapshots reflecting the effect of each action, without
 * touching the network.
 */

import type {
  ExecutionAction,
  GameNode,
  MevThreat,
  OnChainState,
  PoolState,
  SearchConfig,
} from '../types/index.js';
import { constantProductSwap } from '../utils/math.js';
import { hashOnChainState } from '../utils/hash.js';

// ── Builder ─────────────────────────────────────────────────────────

export class GameTreeBuilder {
  private readonly config: SearchConfig;

  constructor(config: SearchConfig) {
    this.config = config;
  }

  /**
   * Build the root of the game tree.  The root represents the current
   * on-chain state before any action is taken.
   */
  buildTree(
    state: OnChainState,
    actions: ExecutionAction[],
    adversaryActions: MevThreat[],
  ): GameNode {
    const root: GameNode = {
      action: null,
      stateHash: hashOnChainState(state),
      children: [],
      score: 0,
      depth: 0,
      isTerminal: false,
      player: 'agent',
    };

    this.expandNodeRecursive(root, state, actions, adversaryActions, 0);
    return root;
  }

  /**
   * Expand a single node by generating all legal child moves for
   * the active player.  Returns the newly created children.
   */
  expandNode(
    node: GameNode,
    state: OnChainState,
    actions: ExecutionAction[],
    adversaryActions: MevThreat[],
  ): GameNode[] {
    if (node.depth >= this.config.maxDepth) {
      node.isTerminal = true;
      return [];
    }

    if (node.player === 'agent') {
      return this.expandAgentNode(node, state, actions, adversaryActions);
    } else {
      return this.expandAdversaryNode(node, state, actions, adversaryActions);
    }
  }

  /**
   * Generate plausible adversary (MEV bot) responses to an agent action.
   */
  generateAdversaryMoves(
    state: OnChainState,
    agentAction: ExecutionAction,
  ): MevThreat[] {
    const threats: MevThreat[] = [];

    // Only certain actions invite MEV
    if (!['swap', 'provide_liquidity', 'remove_liquidity', 'liquidate'].includes(agentAction.kind)) {
      return threats;
    }

    const pool = state.poolStates.get(agentAction.pool);
    if (!pool) return threats;

    // Sandwich threat – more probable for larger trades relative to reserves
    const totalReserve = pool.reserveA + pool.reserveB;
    const tradeRatio = totalReserve > 0n
      ? Number(agentAction.amount) / Number(totalReserve)
      : 0;

    if (tradeRatio > 0.001) {
      const sandwichCost = BigInt(Math.floor(Number(agentAction.amount) * tradeRatio * 0.5));
      threats.push({
        kind: 'sandwich',
        probability: Math.min(tradeRatio * 10, 0.85),
        estimatedCost: sandwichCost,
        sourceAddress: 'SandwichBot1111111111111111111111111111111',
        relatedPool: agentAction.pool,
        description: `Sandwich attack on ${agentAction.kind} of ${agentAction.amount} via pool ${agentAction.pool.slice(0, 8)}…`,
      });
    }

    // Frontrun threat
    if (tradeRatio > 0.005) {
      const frontrunCost = BigInt(Math.floor(Number(agentAction.amount) * tradeRatio * 0.3));
      threats.push({
        kind: 'frontrun',
        probability: Math.min(tradeRatio * 6, 0.7),
        estimatedCost: frontrunCost,
        sourceAddress: 'FrontrunBot11111111111111111111111111111111',
        relatedPool: agentAction.pool,
        description: `Frontrun on ${agentAction.kind} with estimated trade-size advantage`,
      });
    }
