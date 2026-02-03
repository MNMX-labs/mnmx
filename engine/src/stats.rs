use crate::types::SearchStats;

/// Accumulates statistics during a minimax search for diagnostic purposes.
///
/// The engine calls `record_*` methods as it traverses the game tree, and
/// at the end of the search converts to a `SearchStats` for inclusion in
/// the `ExecutionPlan`.
#[derive(Debug, Clone)]
pub struct SearchStatistics {
    nodes_visited: u64,
    nodes_pruned: u64,
    tt_hits: u64,
    tt_misses: u64,
    max_depth_reached: u32,
    depths_completed: Vec<(u32, u64)>, // (depth, time_ms)
    best_move_changes: u32,
    total_children_generated: u64,
    total_interior_nodes: u64,
}

impl SearchStatistics {
    pub fn new() -> Self {
        Self {
            nodes_visited: 0,
            nodes_pruned: 0,
            tt_hits: 0,
            tt_misses: 0,
            max_depth_reached: 0,
            depths_completed: Vec::new(),
            best_move_changes: 0,
            total_children_generated: 0,
            total_interior_nodes: 0,
        }
    }

    /// Record that the search visited a node.
    pub fn record_node_visit(&mut self) {
        self.nodes_visited += 1;
    }

    /// Record that a subtree was pruned (alpha-beta cutoff).
    pub fn record_prune(&mut self) {
        self.nodes_pruned += 1;
    }

    /// Record a transposition table hit.
    pub fn record_tt_hit(&mut self) {
        self.tt_hits += 1;
    }

    /// Record a transposition table miss.
    pub fn record_tt_miss(&mut self) {
        self.tt_misses += 1;
    }

    /// Record that an iterative-deepening iteration completed.
    pub fn record_depth_completed(&mut self, depth: u32, time_ms: u64) {
        if depth > self.max_depth_reached {
            self.max_depth_reached = depth;
        }
        self.depths_completed.push((depth, time_ms));
    }

    /// Record that the best root move changed during iterative deepening.
    pub fn record_best_move_change(&mut self) {
        self.best_move_changes += 1;
    }

    /// Record children generated at an interior node (for branching factor).
    pub fn record_children(&mut self, count: u64) {
        self.total_children_generated += count;
        self.total_interior_nodes += 1;
    }

    /// Convert accumulated stats into the public SearchStats type.
    pub fn to_search_stats(&self) -> SearchStats {
        let total_time: u64 = self
            .depths_completed
            .last()
            .map(|(_, t)| *t)
            .unwrap_or(0);

        SearchStats {
            nodes_explored: self.nodes_visited,
            nodes_pruned: self.nodes_pruned,
            max_depth_reached: self.max_depth_reached,
            time_ms: total_time,
            tt_hits: self.tt_hits,
            tt_misses: self.tt_misses,
            branching_factor: self.effective_branching_factor(),
        }
    }

    /// Fraction of explored nodes that were pruned.
    pub fn pruning_rate(&self) -> f64 {
        let total = self.nodes_visited + self.nodes_pruned;
        if total == 0 {
            0.0
        } else {
            self.nodes_pruned as f64 / total as f64
        }
    }

    /// Throughput: nodes explored per millisecond of search time.
    pub fn nodes_per_second(&self, elapsed_ms: u64) -> f64 {
        if elapsed_ms == 0 {
            return self.nodes_visited as f64;
        }
        (self.nodes_visited as f64 / elapsed_ms as f64) * 1000.0
    }

    /// Effective branching factor: average number of children per interior node.
    pub fn effective_branching_factor(&self) -> f64 {
        if self.total_interior_nodes == 0 {
            return 0.0;
        }
        self.total_children_generated as f64 / self.total_interior_nodes as f64
    }

    /// Number of times the best move changed (instability indicator).
    pub fn best_move_changes(&self) -> u32 {
        self.best_move_changes
    }

    /// Total nodes visited.
    pub fn total_nodes(&self) -> u64 {
        self.nodes_visited
    }

    /// Total nodes pruned.
    pub fn total_pruned(&self) -> u64 {
        self.nodes_pruned
    }

    /// Time profile: how long each depth took.
    pub fn depth_times(&self) -> &[(u32, u64)] {
        &self.depths_completed
    }

    /// TT hit rate.
    pub fn tt_hit_rate(&self) -> f64 {
        let total = self.tt_hits + self.tt_misses;
        if total == 0 {
            0.0
        } else {
            self.tt_hits as f64 / total as f64
        }
    }
}
