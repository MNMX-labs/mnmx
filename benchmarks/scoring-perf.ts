import { normalizeFee, normalizeSpeed, normalizeSlippage, normalizeMevExposure, computeScore } from '../src/router/scoring.js';
import { STRATEGY_WEIGHTS } from '../src/types/index.js';

function generateCandidate() {
  return {
    fee: Math.random() * 50,
    inputAmount: 1000 + Math.random() * 9000,
    speed: Math.random() * 1800,
    slippage: Math.random() * 200,
    mev: Math.random() * 30,
  };
}

function bench(count: number, iters: number) {
  const candidates = Array.from({ length: count }, generateCandidate);
  const start = performance.now();
  for (let i = 0; i < iters; i++) {
    for (const c of candidates) {
      const b = {
        feeScore: normalizeFee(c.fee, c.inputAmount),
        slippageScore: normalizeSlippage(c.slippage),
        speedScore: normalizeSpeed(c.speed),
        reliabilityScore: 0.95,
        mevScore: normalizeMevExposure(c.mev, c.inputAmount),
      };
      computeScore(b, STRATEGY_WEIGHTS.minimax);
    }
  }
  const ms = performance.now() - start;
  console.log(`  ${count} candidates x ${iters} = ${(count * iters / ms * 1000).toFixed(0)} ops/s (${ms.toFixed(1)}ms)`);
}

console.log('Scoring Benchmark');
bench(10, 10000);
bench(100, 1000);
bench(1000, 100);
bench(5000, 50);
