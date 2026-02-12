/**
 * MNMX Plan Executor
 *
 * Translates an ExecutionPlan produced by the minimax engine into
 * real Solana transactions, simulates them, and submits to the cluster
 * with retry logic, priority-fee injection, and compute-budget tuning.
 */

import {
  Connection,
  Keypair,
  Transaction,
  TransactionInstruction,
  SystemProgram,
  PublicKey,
  ComputeBudgetProgram,
  type TransactionSignature,
  sendAndConfirmTransaction,
} from '@solana/web3.js';
import type {
  ExecutionAction,
  ExecutionPlan,
  ExecutionResult,
  SimulationResult,
} from '../types/index.js';

// ── Constants ───────────────────────────────────────────────────────

const MAX_RETRIES = 3;
const BASE_RETRY_DELAY_MS = 500;
const CONFIRMATION_TIMEOUT_MS = 30_000;
const DEFAULT_COMPUTE_UNITS = 400_000;
const DEFAULT_PRIORITY_MICRO_LAMPORTS = 5_000;

// ── Executor ────────────────────────────────────────────────────────

export class PlanExecutor {
  private readonly connection: Connection;
  private readonly wallet: Keypair;

  constructor(connection: Connection, wallet: Keypair) {
    this.connection = connection;
    this.wallet = wallet;
  }

  /**
   * Execute every action in the plan sequentially.  Returns an
   * aggregate result covering all submitted transactions.
   */
  async execute(plan: ExecutionPlan): Promise<ExecutionResult> {
    const signatures: string[] = [];
    const errors: string[] = [];
    let totalCompute = 0;
    let totalFees = 0n;

    for (const action of plan.actions) {
      try {
        const tx = await this.buildTransaction(action);
        const simResult = await this.simulateTransaction(tx);

        if (!simResult.success) {
          errors.push(
            `Simulation failed for ${action.kind}: ${simResult.error ?? 'unknown'}`,
          );
          continue;
        }

        // Adjust compute budget based on simulation
        const adjustedTx = this.adjustComputeBudget(
          tx,
          simResult.computeUnitsConsumed,
        );

        const sig = await this.signAndSend(adjustedTx);
        signatures.push(sig);
        totalCompute += simResult.computeUnitsConsumed;
        totalFees += BigInt(simResult.computeUnitsConsumed) * BigInt(DEFAULT_PRIORITY_MICRO_LAMPORTS);
      } catch (err) {
        const msg = err instanceof Error ? err.message : String(err);
        errors.push(`Execution failed for ${action.kind}: ${msg}`);
      }
    }

    return {
      success: errors.length === 0 && signatures.length > 0,
      signatures,
      errors,
      actualSlippageBps: 0, // would need post-tx analysis to compute
      computeUnitsUsed: totalCompute,
      totalFeeLamports: totalFees,
    };
  }

  /**
   * Build a transaction for a single execution action.
   *
   * In a production system each action kind would construct the
   * appropriate program instruction (e.g., Jupiter swap, Marinade
   * stake).  Here we build a skeleton transaction with compute-budget
   * and priority-fee instructions, plus a placeholder instruction
   * that encodes the action parameters.
   */
  async buildTransaction(action: ExecutionAction): Promise<Transaction> {
    const tx = new Transaction();

    // 1. Compute budget
    tx.add(this.createComputeBudgetInstruction(DEFAULT_COMPUTE_UNITS));

    // 2. Priority fee
    tx.add(this.createPriorityFeeInstruction(DEFAULT_PRIORITY_MICRO_LAMPORTS));

    // 3. Action-specific instruction
    const actionIx = this.buildActionInstruction(action);
    tx.add(actionIx);

    // Fetch recent blockhash
    const { blockhash, lastValidBlockHeight } =
      await this.connection.getLatestBlockhash();
    tx.recentBlockhash = blockhash;
    tx.lastValidBlockHeight = lastValidBlockHeight;
    tx.feePayer = this.wallet.publicKey;

    return tx;
  }

  /**
   * Simulate a transaction without submitting it.
   */
  async simulateTransaction(tx: Transaction): Promise<SimulationResult> {
    try {
      const result = await this.connection.simulateTransaction(tx);
      const value = result.value;
