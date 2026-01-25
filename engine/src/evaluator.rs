use crate::math;
use crate::types::*;

/// Evaluates on-chain positions and actions, producing a score that the
/// minimax engine uses to compare game tree branches.
///
/// Higher scores are better for the Agent; lower scores favor the Adversary.
#[derive(Debug, Clone)]
pub struct PositionEvaluator {
    weights: EvalWeights,
}

impl PositionEvaluator {
    pub fn new(weights: EvalWeights) -> Self {
        Self { weights }
    }

    /// Produce a full evaluation of an action taken from the given state.
    pub fn evaluate(
        &self,
        state: &OnChainState,
        action: &ExecutionAction,
    ) -> EvaluationResult {
        let gas = Self::evaluate_gas_cost(action, state);
        let slippage = self.evaluate_slippage_for_action(action, state);
        let mev = Self::evaluate_mev_exposure(action, &state.pending_transactions);
        let profit = Self::evaluate_profit(action, state);
        let confidence = Self::calculate_confidence(state);

        let breakdown = EvalBreakdown {
            gas_cost: gas,
            slippage_impact: slippage,
            mev_exposure: mev,
            profit_potential: profit,
        };

        let score = self.weights.combine(&breakdown);

        EvaluationResult {
            score,
            breakdown,
            confidence,
        }
    }

    /// Evaluate the gas cost component. Returns a negative value (cost).
    ///
    /// Normalization: we divide the total fee by a baseline of 10_000 lamports
    /// so that a "normal" fee produces a value around -0.5 to -1.0.
    pub fn evaluate_gas_cost(action: &ExecutionAction, _state: &OnChainState) -> f64 {
        let total_fee = action.estimated_total_fee();
        // Baseline: 10_000 lamports = -1.0 score
        let normalized = total_fee as f64 / 10_000.0;
        -normalized
    }

    /// Evaluate slippage impact for a given action.
    fn evaluate_slippage_for_action(
        &self,
        action: &ExecutionAction,
        state: &OnChainState,
    ) -> f64 {
        match Self::find_pool_for_action(action, &state.pool_states) {
            Some(pool) => Self::evaluate_slippage(action, pool),
            None => -0.1, // Small penalty when pool is unknown
        }
    }

    /// Evaluate slippage from a specific pool. Returns a negative value.
    ///
    /// Only Swap, AddLiquidity, and RemoveLiquidity are pool-interactive;
    /// other action kinds incur zero slippage.
    pub fn evaluate_slippage(action: &ExecutionAction, pool: &PoolState) -> f64 {
        match action.kind {
            ActionKind::Swap => {
                let is_a_to_b = action.token_mint == pool.token_a_mint;
                let (reserve_in, reserve_out) = if is_a_to_b {
                    (pool.reserve_a, pool.reserve_b)
                } else {
                    (pool.reserve_b, pool.reserve_a)
                };
                let slippage = math::calculate_slippage(
                    action.amount,
                    reserve_in,
                    reserve_out,
                    pool.fee_rate_bps,
                );
                // Scale: 1% slippage => -1.0
                -(slippage * 100.0)
            }
            ActionKind::AddLiquidity | ActionKind::RemoveLiquidity => {
                let impact = math::calculate_price_impact(
                    action.amount,
                    pool.reserve_a,
                    pool.reserve_b,
                );
                -(impact * 50.0) // Liquidity ops have reduced slippage concern
            }
            _ => 0.0,
        }
    }

    /// Evaluate MEV exposure based on pending mempool transactions.
    ///
    /// Heuristic: count pending transactions that target the same pool,
    /// weight by their fee (high-fee txs are more likely MEV).
    pub fn evaluate_mev_exposure(
        action: &ExecutionAction,
        pending_txs: &[PendingTx],
    ) -> f64 {
        if pending_txs.is_empty() {
            return 0.0;
        }

        let pool = &action.pool_address;
        let competing: Vec<&PendingTx> = pending_txs
            .iter()
            .filter(|tx| tx.to == *pool)
            .collect();

        if competing.is_empty() {
            return 0.0;
        }

        // Each competing tx adds exposure proportional to its fee and amount
        let mut exposure = 0.0;
        for tx in &competing {
            let fee_signal = tx.fee as f64 / 10_000.0;
            let amount_signal = if action.amount > 0 {
                tx.amount as f64 / action.amount as f64
            } else {
                0.0
            };
            // Higher fees and larger amounts relative to ours => more risk
            exposure += fee_signal * (1.0 + amount_signal);
        }

        // Count of competing txs amplifies exposure
        let count_factor = 1.0 + (competing.len() as f64).ln();
        -exposure * count_factor
    }

    /// Evaluate the profit potential of an action.
    ///
    /// For swaps: estimates the output value minus input value.
    /// For other actions: heuristic based on action type.
    pub fn evaluate_profit(action: &ExecutionAction, state: &OnChainState) -> f64 {
        match action.kind {
            ActionKind::Swap => {
                Self::evaluate_swap_profit(action, state)
            }
            ActionKind::Liquidate => {
                // Liquidations are typically profitable; estimate based on amount
                let balance = state
                    .token_balances
                    .get(&action.token_mint)
                    .copied()
                    .unwrap_or(0);
                if action.amount > 0 && balance > 0 {
                    let profit_ratio = action.amount as f64 / balance as f64;
                    profit_ratio * 5.0 // Liquidations can be very profitable
                } else {
                    0.5 // Small positive signal for liquidation opportunities
                }
            }
            ActionKind::AddLiquidity => {
                // Fee income potential from providing liquidity
                if let Some(pool) = Self::find_pool_for_action(action, &state.pool_states) {
                    let pending_count = state.pending_for_pool(&pool.address);
                    let fee_income = math::bps_to_decimal(pool.fee_rate_bps)
                        * action.amount as f64
                        * (1.0 + pending_count as f64 * 0.1);
                    fee_income / 1_000_000.0
                } else {
                    0.0
                }
            }
            ActionKind::RemoveLiquidity => {
                // Recovering liquidity: small positive unless pool is dangerous
                0.2
            }
            ActionKind::Transfer => {
                // Transfers don't directly profit, but may enable other strategies
                0.0
            }
            ActionKind::Stake => {
                // Staking earns yield; estimate annualized yield / time
                0.3
            }
            ActionKind::Unstake => {
                // Unstaking is often done to redeploy capital
                0.1
            }
        }
    }
