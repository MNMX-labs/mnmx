// ─────────────────────────────────────────────────────────────
// Chain Configuration Registry
// Centralized chain metadata and RPC endpoints
// ─────────────────────────────────────────────────────────────

export interface ChainConfig {
  id: number;
  name: string;
  shortName: string;
  nativeCurrency: { symbol: string; decimals: number };
  blockTimeMs: number;
  confirmations: number;
  explorerUrl: string;
}

export const CHAIN_CONFIGS: Record<number, ChainConfig> = {
  1: {
    id: 1, name: 'Ethereum', shortName: 'ETH',
    nativeCurrency: { symbol: 'ETH', decimals: 18 },
    blockTimeMs: 12_000, confirmations: 12,
    explorerUrl: 'https://etherscan.io',
  },
  42161: {
    id: 42161, name: 'Arbitrum One', shortName: 'ARB',
    nativeCurrency: { symbol: 'ETH', decimals: 18 },
    blockTimeMs: 250, confirmations: 1,
    explorerUrl: 'https://arbiscan.io',
  },
  10: {
    id: 10, name: 'Optimism', shortName: 'OP',
    nativeCurrency: { symbol: 'ETH', decimals: 18 },
    blockTimeMs: 2_000, confirmations: 1,
    explorerUrl: 'https://optimistic.etherscan.io',
  },
  8453: {
    id: 8453, name: 'Base', shortName: 'BASE',
    nativeCurrency: { symbol: 'ETH', decimals: 18 },
    blockTimeMs: 2_000, confirmations: 1,
    explorerUrl: 'https://basescan.org',
  },
  137: {
    id: 137, name: 'Polygon', shortName: 'POL',
    nativeCurrency: { symbol: 'POL', decimals: 18 },
    blockTimeMs: 2_000, confirmations: 32,
    explorerUrl: 'https://polygonscan.com',
  },
  43114: {
    id: 43114, name: 'Avalanche', shortName: 'AVAX',
    nativeCurrency: { symbol: 'AVAX', decimals: 18 },
    blockTimeMs: 2_000, confirmations: 1,
    explorerUrl: 'https://snowtrace.io',
  },
  56: {
    id: 56, name: 'BNB Chain', shortName: 'BNB',
    nativeCurrency: { symbol: 'BNB', decimals: 18 },
    blockTimeMs: 3_000, confirmations: 15,
    explorerUrl: 'https://bscscan.com',
  },
};

export function getChainConfig(chainId: number): ChainConfig | undefined {
  return CHAIN_CONFIGS[chainId];
}

export function getExplorerTxUrl(chainId: number, txHash: string): string {
  const config = CHAIN_CONFIGS[chainId];
  if (!config) return '';
  return `${config.explorerUrl}/tx/${txHash}`;
}

export function getSupportedChainIds(): number[] {
  return Object.keys(CHAIN_CONFIGS).map(Number);
}
