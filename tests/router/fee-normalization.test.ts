import { describe, it, expect } from 'vitest';
import { normalizeFee } from '../../src/router/scoring.js';

describe('Fee Normalization Edge Cases', () => {
  it('handles sub-dollar transfers', () => {
    const score = normalizeFee(0.001, 0.5);
    expect(score).toBeGreaterThan(0);
    expect(score).toBeLessThanOrEqual(1);
  });

  it('handles fee larger than input', () => {
    const score = normalizeFee(10, 5);
    expect(score).toBe(0);
  });

  it('normalizes proportionally', () => {
    const low = normalizeFee(1, 1000);
    const high = normalizeFee(50, 1000);
    expect(low).toBeGreaterThan(high);
  });

  it('perfect zero fee returns 1', () => {
    const score = normalizeFee(0, 100);
    expect(score).toBe(1);
  });
});
