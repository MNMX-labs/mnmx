import { describe, it, expect } from 'vitest';
import {
  minimaxSearch,
  minimaxSearchWithPruning,
  iterativeDeepening,
} from '../../src/router/minimax.js';
import type { MinimaxOptions } from '../../src/router/minimax.js';
import type { CandidatePath, Token, BridgeQuote, Chain } from '../../src/types/index.js';
import { DEFAULT_ROUTER_CONFIG } from '../../src/types/index.js';

function makeToken(symbol: string, chain: Chain): Token {
  return { symbol, chain, decimals: 18, address: `0x${chain}_${symbol}` };
}

function makeQuote(bridge: string, input: number, output: number, fee: number, time: number): BridgeQuote {
  return {
    bridge,
    inputAmount: input.toFixed(6),
    outputAmount: output.toFixed(6),
    fee: fee.toFixed(6),
    estimatedTime: time,
    liquidityDepth: 5_000_000,
    expiresAt: Date.now() + 60_000,
    slippageBps: 10,
  };
}

function makeCandidate(
  chains: Chain[],
  bridges: string[],
  quotes: BridgeQuote[],
  roughScore: number,
): CandidatePath {
  const tokens: Token[] = chains.map((c) => makeToken('USDC', c));
  return {
    chains,
    bridges,
    tokens,
    quotes,
    estimatedFee: quotes.reduce((s, q) => s + parseFloat(q.fee), 0),
    estimatedTime: quotes.reduce((s, q) => s + q.estimatedTime, 0),
    roughScore,
  };
}

const defaultOptions: MinimaxOptions = {
  maxDepth: 3,
  weights: DEFAULT_ROUTER_CONFIG.weights,
  adversarialModel: DEFAULT_ROUTER_CONFIG.adversarialModel,
  strategy: 'minimax',
};

describe('minimax search', () => {
  const candidates: CandidatePath[] = [
    makeCandidate(
      ['ethereum', 'solana'],
      ['wormhole'],
      [makeQuote('wormhole', 1000, 993, 7, 900)],
      0.993,
    ),
    makeCandidate(
      ['ethereum', 'solana'],
      ['debridge'],
      [makeQuote('debridge', 1000, 995, 5, 600)],
      0.995,
    ),
    makeCandidate(
      ['ethereum', 'arbitrum', 'solana'],
      ['debridge', 'wormhole'],
      [makeQuote('debridge', 1000, 997, 3, 480), makeQuote('wormhole', 997, 990, 7, 900)],
      0.990,
    ),
  ];

  it('finds optimal route', () => {
