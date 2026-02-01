use crate::math;
use crate::types::*;

/// Known MEV bot address prefixes on Solana.
/// These are patterns commonly seen in MEV bot program addresses.
const KNOWN_MEV_PREFIXES: &[&str] = &[
    "JUP",    // Jupiter aggregator bots
    "MEV",    // Generic MEV label
    "ARB",    // Arbitrage bots
    "SAND",   // Sandwich bots
    "FL4SH",  // Flash loan bots
    "B0T",    // Common bot naming
    "SNIP3R", // Sniper bots
    "jito",   // Jito MEV
    "BLXR",   // bloXroute relayers
];

/// Minimum trade size (as fraction of pool reserve) to consider MEV-worthy.
const MIN_MEV_FRACTION: f64 = 0.001;

/// Detects potential MEV threats for a given action by analyzing the
/// mempool, pool states, and known bot patterns.
#[derive(Debug, Clone)]
pub struct MevDetector {
    /// Sensitivity multiplier. Higher = more conservative (flags more threats).
    sensitivity: f64,
    /// Minimum probability threshold to report a threat.
    min_probability: f64,
}

impl MevDetector {
    pub fn new() -> Self {
        Self {
            sensitivity: 1.0,
            min_probability: 0.05,
        }
    }

    /// Create a detector with custom sensitivity.
    pub fn with_sensitivity(sensitivity: f64) -> Self {
        Self {
            sensitivity: math::clamp_f64(sensitivity, 0.1, 10.0),
            min_probability: 0.05,
        }
    }

    /// Analyze all MEV threat vectors for a given action.
    pub fn detect_threats(
        &self,
        action: &ExecutionAction,
        state: &OnChainState,
    ) -> Vec<MevThreat> {
        let mut threats = Vec::new();

        // Only pool-interactive actions are MEV targets
        match action.kind {
            ActionKind::Swap | ActionKind::AddLiquidity | ActionKind::RemoveLiquidity => {}
            _ => return threats,
        }

        let pools = &state.pool_states;
        let pending = &state.pending_transactions;

        if let Some(threat) = self.analyze_sandwich_risk(action, pending, pools) {
            if threat.probability >= self.min_probability {
                threats.push(threat);
            }
        }

        if let Some(threat) = self.analyze_frontrun_risk(action, pending) {
            if threat.probability >= self.min_probability {
                threats.push(threat);
            }
        }

        if let Some(threat) = self.analyze_backrun_risk(action, pending) {
            if threat.probability >= self.min_probability {
                threats.push(threat);
            }
        }

        if let Some(pool) = pools.iter().find(|p| p.address == action.pool_address) {
            if let Some(threat) = self.analyze_jit_risk(action, pool) {
                if threat.probability >= self.min_probability {
                    threats.push(threat);
                }
            }
        }

        threats
    }
