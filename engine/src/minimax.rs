use std::time::Instant;

use crate::evaluator::PositionEvaluator;
use crate::game_tree::GameTreeBuilder;
use crate::mev::MevDetector;
use crate::move_ordering::MoveOrderer;
use crate::stats::SearchStatistics;
use crate::time_manager::{ExtendReason, TimeManager};
use crate::transposition::TranspositionTable;
use crate::types::*;

/// The core minimax search engine with alpha-beta pruning, iterative
/// deepening, transposition table, aspiration windows, and move ordering.
///
/// Usage:
/// ```ignore
/// let config = SearchConfig::default();
/// let mut engine = MinimaxEngine::new(config);
/// let plan = engine.search(&state, &actions);
/// ```
pub struct MinimaxEngine {
    config: SearchConfig,
    evaluator: PositionEvaluator,
    _tree_builder: GameTreeBuilder,
    move_orderer: MoveOrderer,
    transposition_table: TranspositionTable,
    mev_detector: MevDetector,
    time_manager: TimeManager,
    stats: SearchStatistics,
    start_time: Option<Instant>,
    aborted: bool,
}

impl MinimaxEngine {
    pub fn new(config: SearchConfig) -> Self {
        let evaluator = PositionEvaluator::new(config.eval_weights.clone());
        let tree_builder = GameTreeBuilder::new(evaluator.clone());
        let time_manager = TimeManager::new(&config);

        Self {
            evaluator,
            _tree_builder: tree_builder,
            move_orderer: MoveOrderer::new(),
            transposition_table: TranspositionTable::new(100_000),
            mev_detector: MevDetector::new(),
            time_manager,
            stats: SearchStatistics::new(),
            start_time: None,
            aborted: false,
            config,
        }
    }

    /// Run iterative-deepening minimax with alpha-beta pruning.
    ///
    /// Returns an `ExecutionPlan` containing the best sequence of actions
    /// found within the time budget.
    pub fn search(
        &mut self,
        state: &OnChainState,
        actions: &[ExecutionAction],
    ) -> ExecutionPlan {
        self.stats = SearchStatistics::new();
        self.aborted = false;
        self.start_time = Some(Instant::now());

        if self.config.move_ordering_enabled {
            self.move_orderer.reset();
        }

        self.transposition_table.new_search();

        if actions.is_empty() {
            return ExecutionPlan::empty(self.stats.to_search_stats());
        }

        // Detect threats for all candidate actions
        let threats: Vec<MevThreat> = actions
            .iter()
            .flat_map(|a| self.mev_detector.detect_threats(a, state))
            .collect();

        let mut best_actions: Vec<ExecutionAction> = Vec::new();
        let mut best_score = f64::NEG_INFINITY;
        let mut previous_best_score = f64::NEG_INFINITY;

        // Iterative deepening: search from depth 1 up to max_depth
        for depth in 1..=self.config.max_depth {
            if self.should_stop_search(depth) {
                break;
            }
