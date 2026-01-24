import { describe, it, expect } from 'vitest';
import { normalizeFee, normalizeSpeed, normalizeReliability, normalizeSlippage, normalizeMevExposure } from '../../src/router/scoring.js';

describe('Scoring Weight Edge Cases', () => {
  describe('normalizeFee', () => {
    it('returns 1.0 for zero fee', () => {
      expect(normalizeFee(0, 1000)).toBe(1);
    });

    it('returns 0 for fee exceeding max ratio', () => {
      expect(normalizeFee(200, 1000)).toBe(0);
    });

    it('handles zero input amount', () => {
      expect(normalizeFee(10, 0)).toBe(0);
    });

    it('handles negative input', () => {
      expect(normalizeFee(10, -100)).toBe(0);
    });

    it('scales linearly between 0 and max', () => {
      const score = normalizeFee(50, 1000); // 5% fee, max is 10%
      expect(score).toBeCloseTo(0.5, 1);
    });
  });

  describe('normalizeSpeed', () => {
    it('returns 1.0 for instant execution', () => {
      expect(normalizeSpeed(0)).toBe(1);
    });

    it('returns 0 for max time exceeded', () => {
      expect(normalizeSpeed(3600)).toBe(0);
    });

    it('handles negative time gracefully', () => {
      expect(normalizeSpeed(-10)).toBe(1);
    });

    it('mid-range time produces mid-range score', () => {
      const score = normalizeSpeed(900); // half of 1800
      expect(score).toBeCloseTo(0.5, 1);
    });
  });

  describe('normalizeSlippage', () => {
    it('returns 1.0 for zero slippage', () => {
      expect(normalizeSlippage(0)).toBe(1);
    });

    it('returns 0 for max slippage', () => {
      expect(normalizeSlippage(200)).toBe(0);
    });
  });

  describe('normalizeMevExposure', () => {
    it('returns 1.0 for zero MEV', () => {
      expect(normalizeMevExposure(0, 1000)).toBe(1);
    });

    it('returns 0 for extreme MEV exposure', () => {
      expect(normalizeMevExposure(100, 1000)).toBe(0);
    });
  });
});
