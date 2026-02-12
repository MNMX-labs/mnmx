/**
 * MNMX Solana State Reader
 *
 * Reads relevant on-chain state from a Solana cluster and packages it
 * into the engine's OnChainState format.  Handles token accounts,
 * liquidity-pool reserves, recent transactions, and slot tracking.
 */

import {
  Connection,
  PublicKey,
  type AccountInfo,
  type ParsedAccountData,
} from '@solana/web3.js';
import { TOKEN_PROGRAM_ID } from '@solana/spl-token';
import type { OnChainState, PendingTx, PoolState } from '../types/index.js';

// ── Constants ───────────────────────────────────────────────────────

/** Layout byte-offsets for a generic Raydium-style AMM pool account. */
const POOL_RESERVE_OFFSET_A = 64;
const POOL_RESERVE_OFFSET_B = 72;
const POOL_FEE_OFFSET = 80;
const POOL_MINT_A_OFFSET = 8;
const POOL_MINT_B_OFFSET = 40;

// ── State Reader ────────────────────────────────────────────────────

export class StateReader {
  private readonly connection: Connection;

  constructor(connection: Connection) {
    this.connection = connection;
  }

  /**
   * Fetch a complete snapshot of on-chain state relevant to the given
   * wallet and set of liquidity pools.
   */
  async getOnChainState(
    walletAddress: PublicKey,
    pools: PublicKey[],
  ): Promise<OnChainState> {
    const [tokenBalances, poolStates, pendingTxs, slot] = await Promise.all([
      this.getTokenBalances(walletAddress),
      this.getAllPoolStates(pools),
      this.getRecentTransactions(25),
      this.getCurrentSlot(),
    ]);

    return {
      tokenBalances,
      poolStates,
      pendingTransactions: pendingTxs,
      slot,
      timestamp: Date.now(),
    };
  }

  /**
   * Fetch all SPL token balances for a wallet, keyed by mint address.
   */
  async getTokenBalances(wallet: PublicKey): Promise<Map<string, bigint>> {
    const balances = new Map<string, bigint>();

    try {
      const tokenAccounts = await this.connection.getParsedTokenAccountsByOwner(
        wallet,
        { programId: TOKEN_PROGRAM_ID },
      );

      for (const { account } of tokenAccounts.value) {
        const parsed = account.data as ParsedAccountData;
        const info = parsed.parsed?.info;
        if (!info) continue;

        const mint: string = info.mint;
        const amountStr: string = info.tokenAmount?.amount ?? '0';
        const amount = BigInt(amountStr);

        // Accumulate in case of multiple ATAs for the same mint
        const existing = balances.get(mint) ?? 0n;
        balances.set(mint, existing + amount);
      }

      // Also include native SOL balance
      const lamports = await this.connection.getBalance(wallet);
      balances.set('SOL', BigInt(lamports));
    } catch (err) {
      // Return whatever we managed to collect
      console.error('[StateReader] getTokenBalances error:', err);
    }

    return balances;
  }

  /**
   * Fetch the on-chain state of a single liquidity pool.
   *
   * This implementation reads the raw account data and parses reserve
   * amounts from fixed offsets.  In production you would use the
   * pool program's IDL-based deserialization.
   */
  async getPoolState(pool: PublicKey): Promise<PoolState> {
    const accountInfo = await this.connection.getAccountInfo(pool);

    if (!accountInfo || !accountInfo.data) {
      return this.emptyPoolState(pool.toBase58());
    }

    return this.parsePoolAccount(pool.toBase58(), accountInfo);
  }

  /**
   * Fetch recent confirmed transactions as a proxy for mempool
   * activity.  True mempool access requires a Geyser/Jito integration;
   * this provides a reasonable fallback.
   */
  async getRecentTransactions(count: number): Promise<PendingTx[]> {
    const txs: PendingTx[] = [];

    try {
      const signatures = await this.connection.getSignaturesForAddress(
        new PublicKey('11111111111111111111111111111111'), // system program
        { limit: count },
      );

      for (const sig of signatures) {
        txs.push({
          signature: sig.signature,
          fromAddress: '',
          toAddress: '',
          programId: '11111111111111111111111111111111',
          data: new Uint8Array(0),
          lamports: 0n,
          slot: sig.slot,
        });
      }
    } catch {
      // Non-critical – return empty list
    }

    return txs;
  }

  /**
   * Get the current slot number from the cluster.
   */
  async getCurrentSlot(): Promise<number> {
    try {
      return await this.connection.getSlot();
    } catch {
      return 0;
    }
  }

  // ── Private ─────────────────────────────────────────────────────

  private async getAllPoolStates(
    pools: PublicKey[],
  ): Promise<Map<string, PoolState>> {
    const states = new Map<string, PoolState>();
    const results = await Promise.allSettled(
      pools.map((p) => this.getPoolState(p)),
    );

    for (let i = 0; i < pools.length; i++) {
      const result = results[i]!;
      const addr = pools[i]!.toBase58();
      if (result.status === 'fulfilled') {
        states.set(addr, result.value);
      } else {
        states.set(addr, this.emptyPoolState(addr));
      }
    }

    return states;
  }

  private parsePoolAccount(
    address: string,
    info: AccountInfo<Buffer>,
  ): PoolState {
    const data = info.data;

    // Guard against undersized accounts
    if (data.length < POOL_FEE_OFFSET + 4) {
      return this.emptyPoolState(address);
    }

    try {
      const tokenMintA = new PublicKey(
        data.subarray(POOL_MINT_A_OFFSET, POOL_MINT_A_OFFSET + 32),
      ).toBase58();
      const tokenMintB = new PublicKey(
        data.subarray(POOL_MINT_B_OFFSET, POOL_MINT_B_OFFSET + 32),
      ).toBase58();
      const reserveA = data.readBigUInt64LE(POOL_RESERVE_OFFSET_A);
      const reserveB = data.readBigUInt64LE(POOL_RESERVE_OFFSET_B);
      const feeBps = data.readUInt16LE(POOL_FEE_OFFSET);

      return { address, tokenMintA, tokenMintB, reserveA, reserveB, feeBps };
    } catch {
      return this.emptyPoolState(address);
    }
  }

  private emptyPoolState(address: string): PoolState {
    return {
      address,
      tokenMintA: '',
      tokenMintB: '',
      reserveA: 0n,
      reserveB: 0n,
      feeBps: 30,
    };
  }
}
