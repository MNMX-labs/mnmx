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
