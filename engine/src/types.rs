use serde::{Deserialize, Serialize};
use std::collections::HashMap;

/// Which side of the game tree we are evaluating.
/// Agent = the autonomous on-chain agent (maximizing player).
/// Adversary = MEV bots / extractors (minimizing player).
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
pub enum Player {
    Agent,
    Adversary,
}

impl Player {
    pub fn opponent(&self) -> Player {
        match self {
            Player::Agent => Player::Adversary,
            Player::Adversary => Player::Agent,
        }
    }
}

/// The kind of on-chain action that can be taken.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
pub enum ActionKind {
    Swap,
    Transfer,
    Stake,
    Unstake,
    Liquidate,
    AddLiquidity,
    RemoveLiquidity,
}

impl ActionKind {
    /// Returns a deterministic ordering index used by move ordering heuristics.
    pub fn priority_index(&self) -> u32 {
        match self {
            ActionKind::Liquidate => 0,
            ActionKind::Swap => 1,
            ActionKind::RemoveLiquidity => 2,
            ActionKind::AddLiquidity => 3,
            ActionKind::Transfer => 4,
            ActionKind::Unstake => 5,
            ActionKind::Stake => 6,
        }
    }

    /// Returns a human-readable label for logging.
    pub fn label(&self) -> &'static str {
        match self {
            ActionKind::Swap => "swap",
            ActionKind::Transfer => "transfer",
            ActionKind::Stake => "stake",
            ActionKind::Unstake => "unstake",
            ActionKind::Liquidate => "liquidate",
            ActionKind::AddLiquidity => "add_liq",
            ActionKind::RemoveLiquidity => "rem_liq",
        }
    }
}

/// A concrete on-chain action the agent can execute.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct ExecutionAction {
    pub kind: ActionKind,
    pub token_mint: String,
    pub amount: u64,
    pub destination: String,
    pub slippage_bps: u16,
    pub pool_address: String,
    pub priority_fee: u64,
}

impl ExecutionAction {
    pub fn new(
        kind: ActionKind,
        token_mint: &str,
        amount: u64,
        destination: &str,
        slippage_bps: u16,
        pool_address: &str,
        priority_fee: u64,
    ) -> Self {
        Self {
            kind,
            token_mint: token_mint.to_string(),
            amount,
            destination: destination.to_string(),
            slippage_bps,
            pool_address: pool_address.to_string(),
            priority_fee,
        }
    }

    /// Produce a compact key for hashing / history tables.
    pub fn action_key(&self) -> String {
        format!(
            "{}:{}:{}:{}",
            self.kind.label(),
            self.token_mint,
            self.amount,
            self.pool_address
        )
    }

    /// Estimated total cost in lamports (priority fee + base fee estimate).
    pub fn estimated_total_fee(&self) -> u64 {
        self.priority_fee.saturating_add(5000)
    }
}

/// A single node in the game tree.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct GameNode {
    pub action: Option<ExecutionAction>,
    pub state_hash: String,
    pub children: Vec<GameNode>,
    pub score: f64,
    pub depth: u32,
    pub is_terminal: bool,
    pub player: Player,
}

impl GameNode {
    pub fn new_root(state_hash: String) -> Self {
        Self {
            action: None,
            state_hash,
            children: Vec::new(),
            score: 0.0,
            depth: 0,
            is_terminal: false,
            player: Player::Agent,
        }
    }

    pub fn new_child(
        action: ExecutionAction,
        state_hash: String,
        depth: u32,
        player: Player,
    ) -> Self {
        Self {
            action: Some(action),
            state_hash,
            children: Vec::new(),
            score: 0.0,
            depth,
            is_terminal: false,
            player,
        }
    }

    /// Total number of nodes in this subtree, including self.
    pub fn subtree_size(&self) -> usize {
        1 + self.children.iter().map(|c| c.subtree_size()).sum::<usize>()
    }

    /// Maximum depth found in this subtree.
    pub fn max_depth(&self) -> u32 {
        if self.children.is_empty() {
            self.depth
        } else {
            self.children.iter().map(|c| c.max_depth()).max().unwrap_or(self.depth)
        }
    }
}

/// Current on-chain state snapshot used for evaluation.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct OnChainState {
    pub token_balances: HashMap<String, u64>,
    pub pool_states: Vec<PoolState>,
    pub pending_transactions: Vec<PendingTx>,
    pub slot: u64,
    pub block_time: i64,
}

impl OnChainState {
    pub fn new(slot: u64, block_time: i64) -> Self {
        Self {
            token_balances: HashMap::new(),
            pool_states: Vec::new(),
            pending_transactions: Vec::new(),
            slot,
            block_time,
        }
    }

    /// Total value of all token balances (simple sum of raw amounts).
    pub fn total_balance(&self) -> u64 {
        self.token_balances.values().sum()
    }

    /// Find a pool by its address.
    pub fn find_pool(&self, address: &str) -> Option<&PoolState> {
        self.pool_states.iter().find(|p| p.address == address)
    }

    /// Find a pool that contains a given token mint on either side.
    pub fn find_pool_for_mint(&self, mint: &str) -> Option<&PoolState> {
        self.pool_states
            .iter()
            .find(|p| p.token_a_mint == mint || p.token_b_mint == mint)
    }

    /// Number of pending transactions targeting a specific pool.
    pub fn pending_for_pool(&self, pool_address: &str) -> usize {
        self.pending_transactions
            .iter()
            .filter(|tx| tx.to == pool_address)
            .count()
    }
}

/// State of a single AMM liquidity pool.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct PoolState {
    pub address: String,
    pub reserve_a: u64,
    pub reserve_b: u64,
    pub fee_rate_bps: u16,
    pub token_a_mint: String,
    pub token_b_mint: String,
    pub liquidity: u128,
    pub sqrt_price: u128,
}

impl PoolState {
    pub fn new(
        address: &str,
        reserve_a: u64,
        reserve_b: u64,
        fee_rate_bps: u16,
        token_a_mint: &str,
        token_b_mint: &str,
    ) -> Self {
        let liquidity = (reserve_a as u128).saturating_mul(reserve_b as u128);
        let sqrt_price = if reserve_a > 0 {
            crate::math::isqrt(
                ((reserve_b as u128) << 64) / (reserve_a as u128),
            )
        } else {
            0
        };
        Self {
            address: address.to_string(),
            reserve_a,
            reserve_b,
            fee_rate_bps,
            token_a_mint: token_a_mint.to_string(),
            token_b_mint: token_b_mint.to_string(),
            liquidity,
            sqrt_price,
        }
    }

    /// Instantaneous price of token A denominated in token B.
    pub fn price_a_in_b(&self) -> f64 {
        if self.reserve_a == 0 {
            return 0.0;
        }
        self.reserve_b as f64 / self.reserve_a as f64
    }

    /// Total value locked (sum of both reserves).
    pub fn tvl(&self) -> u64 {
        self.reserve_a.saturating_add(self.reserve_b)
    }
}

/// A pending (unconfirmed) transaction observed in the mempool.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct PendingTx {
    pub signature: String,
    pub from: String,
    pub to: String,
    pub amount: u64,
    pub instruction_data: Vec<u8>,
    pub slot: u64,
    pub fee: u64,
}

impl PendingTx {
    pub fn new(
        signature: &str,
        from: &str,
        to: &str,
        amount: u64,
        slot: u64,
        fee: u64,
    ) -> Self {
        Self {
            signature: signature.to_string(),
            from: from.to_string(),
            to: to.to_string(),
            amount,
            instruction_data: Vec::new(),
            slot,
            fee,
        }
    }

    /// Whether this transaction has a higher fee than another, indicating
    /// it may be trying to front-run.
    pub fn outbids(&self, other: &PendingTx) -> bool {
        self.fee > other.fee
    }
}

/// The result of evaluating a position/action pair.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct EvaluationResult {
    pub score: f64,
    pub breakdown: EvalBreakdown,
    pub confidence: f64,
}

impl EvaluationResult {
    pub fn zero() -> Self {
        Self {
            score: 0.0,
            breakdown: EvalBreakdown::zero(),
            confidence: 0.0,
        }
    }
}

/// Detailed breakdown of an evaluation score.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct EvalBreakdown {
    pub gas_cost: f64,
    pub slippage_impact: f64,
    pub mev_exposure: f64,
    pub profit_potential: f64,
}

impl EvalBreakdown {
    pub fn zero() -> Self {
        Self {
            gas_cost: 0.0,
            slippage_impact: 0.0,
            mev_exposure: 0.0,
            profit_potential: 0.0,
        }
    }

    /// Sum of all component scores (unsigned for inspection).
    pub fn total_magnitude(&self) -> f64 {
        self.gas_cost.abs()
            + self.slippage_impact.abs()
            + self.mev_exposure.abs()
            + self.profit_potential.abs()
    }
}

/// Configuration for the minimax search.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SearchConfig {
    pub max_depth: u32,
    pub alpha_beta_enabled: bool,
    pub time_limit_ms: u64,
    pub eval_weights: EvalWeights,
    pub transposition_enabled: bool,
    pub move_ordering_enabled: bool,
}

impl Default for SearchConfig {
    fn default() -> Self {
        Self {
            max_depth: 6,
            alpha_beta_enabled: true,
            time_limit_ms: 2000,
            eval_weights: EvalWeights::default(),
            transposition_enabled: true,
            move_ordering_enabled: true,
        }
    }
}

impl SearchConfig {
    pub fn fast() -> Self {
        Self {
            max_depth: 3,
            time_limit_ms: 500,
            ..Self::default()
        }
    }

    pub fn deep() -> Self {
        Self {
            max_depth: 10,
            time_limit_ms: 10000,
            ..Self::default()
        }
    }
}

/// Weight multipliers for each evaluation component.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct EvalWeights {
    pub gas: f64,
    pub slippage: f64,
    pub mev: f64,
    pub profit: f64,
}

impl Default for EvalWeights {
    fn default() -> Self {
        Self {
            gas: 1.0,
            slippage: 1.5,
            mev: 2.0,
            profit: 3.0,
        }
    }
}

impl EvalWeights {
    /// Combine an eval breakdown into a single weighted score.
    pub fn combine(&self, b: &EvalBreakdown) -> f64 {
        b.gas_cost * self.gas
            + b.slippage_impact * self.slippage
            + b.mev_exposure * self.mev
            + b.profit_potential * self.profit
    }
}

/// The final output of a search: an ordered plan of actions.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ExecutionPlan {
    pub actions: Vec<ExecutionAction>,
    pub expected_score: f64,
    pub total_cost: u64,
    pub search_stats: SearchStats,
}

impl ExecutionPlan {
    pub fn empty(stats: SearchStats) -> Self {
        Self {
            actions: Vec::new(),
            expected_score: 0.0,
            total_cost: 0,
            search_stats: stats,
        }
    }
}
