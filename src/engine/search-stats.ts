/**
 * MNMX Search Statistics
 *
 * Collects fine-grained telemetry during minimax search to support
 * performance analysis, tuning, and debugging. Tracks node visits,
 * pruning rates, transposition table effectiveness, branching factors,
 * and per-depth timing.
 */

// ── Event Types ──────────────────────────────────────────────────────

export type SearchEventKind =
  | 'node_visited'
  | 'node_pruned'
  | 'tt_hit'
  | 'tt_miss'
  | 'depth_completed'
  | 'best_move_changed';

export interface SearchEvent {
  readonly kind: SearchEventKind;
  readonly depth: number;
  readonly timestamp: number;
  /** Optional metadata attached to the event. */
  readonly meta?: Record<string, number | string>;
}

// ── Report Types ─────────────────────────────────────────────────────

export interface DepthReport {
  readonly depth: number;
  readonly nodesVisited: number;
  readonly nodesPruned: number;
  readonly ttHits: number;
  readonly ttMisses: number;
  readonly bestMoveChanges: number;
  readonly startTimestamp: number;
  readonly endTimestamp: number;
  readonly durationMs: number;
}

export interface SearchReport {
  readonly totalNodes: number;
  readonly totalPruned: number;
  readonly pruningRate: number;
  readonly totalTtHits: number;
  readonly totalTtMisses: number;
  readonly ttHitRate: number;
  readonly effectiveBranchingFactor: number;
  readonly maxDepthReached: number;
  readonly depthReports: DepthReport[];
  readonly totalTimeMs: number;
  readonly nodesPerSecond: number;
  readonly bestMoveChanges: number;
}

// ── Search Statistics ────────────────────────────────────────────────

export class SearchStatistics {
  private readonly events: SearchEvent[] = [];

  // Per-depth accumulators for efficient report generation
  private readonly depthNodes: Map<number, number> = new Map();
  private readonly depthPruned: Map<number, number> = new Map();
  private readonly depthTtHits: Map<number, number> = new Map();
  private readonly depthTtMisses: Map<number, number> = new Map();
  private readonly depthBestMoveChanges: Map<number, number> = new Map();
  private readonly depthFirstTimestamp: Map<number, number> = new Map();
  private readonly depthLastTimestamp: Map<number, number> = new Map();

  private totalNodes = 0;
  private totalPruned = 0;
  private totalTtHits = 0;
  private totalTtMisses = 0;
  private totalBestMoveChanges = 0;
  private maxDepthSeen = 0;
  private firstEventTimestamp = 0;
  private lastEventTimestamp = 0;

  /**
   * Record a search event. Incrementally updates internal counters
   * so that report generation is O(depth) rather than O(events).
   */
  track(event: SearchEvent): void {
    this.events.push(event);

    if (this.firstEventTimestamp === 0) {
      this.firstEventTimestamp = event.timestamp;
    }
    this.lastEventTimestamp = event.timestamp;

    if (event.depth > this.maxDepthSeen) {
      this.maxDepthSeen = event.depth;
    }

    // Update depth-level first/last timestamps
    if (!this.depthFirstTimestamp.has(event.depth)) {
      this.depthFirstTimestamp.set(event.depth, event.timestamp);
    }
    this.depthLastTimestamp.set(event.depth, event.timestamp);

    switch (event.kind) {
      case 'node_visited':
        this.totalNodes++;
        this.increment(this.depthNodes, event.depth);
        break;

      case 'node_pruned':
        this.totalPruned++;
        this.increment(this.depthPruned, event.depth);
        break;

      case 'tt_hit':
        this.totalTtHits++;
        this.increment(this.depthTtHits, event.depth);
        break;

      case 'tt_miss':
        this.totalTtMisses++;
        this.increment(this.depthTtMisses, event.depth);
        break;

      case 'best_move_changed':
        this.totalBestMoveChanges++;
        this.increment(this.depthBestMoveChanges, event.depth);
        break;

      case 'depth_completed':
        // No special accumulator; the depth timestamp tracking is sufficient.
        break;
    }
  }

  /**
   * Generate a comprehensive search report from all tracked events.
   */
  getReport(): SearchReport {
    const totalTimeMs = this.lastEventTimestamp - this.firstEventTimestamp;
    const nodesPerSecond =
      totalTimeMs > 0 ? (this.totalNodes / totalTimeMs) * 1000 : 0;

    const ttLookups = this.totalTtHits + this.totalTtMisses;
    const ttHitRate = ttLookups > 0 ? this.totalTtHits / ttLookups : 0;

    const totalEvaluated = this.totalNodes + this.totalPruned;
    const pruningRate =
      totalEvaluated > 0 ? this.totalPruned / totalEvaluated : 0;

    const ebf = this.computeEffectiveBranchingFactor();

    const depthReports = this.buildDepthReports();

    return {
      totalNodes: this.totalNodes,
      totalPruned: this.totalPruned,
      pruningRate,
      totalTtHits: this.totalTtHits,
      totalTtMisses: this.totalTtMisses,
      ttHitRate,
      effectiveBranchingFactor: ebf,
      maxDepthReached: this.maxDepthSeen,
      depthReports,
      totalTimeMs,
      nodesPerSecond,
      bestMoveChanges: this.totalBestMoveChanges,
    };
  }

  /**
   * Reset all statistics for a new search session.
   */
  reset(): void {
    this.events.length = 0;
    this.depthNodes.clear();
    this.depthPruned.clear();
    this.depthTtHits.clear();
    this.depthTtMisses.clear();
    this.depthBestMoveChanges.clear();
    this.depthFirstTimestamp.clear();
    this.depthLastTimestamp.clear();
    this.totalNodes = 0;
    this.totalPruned = 0;
    this.totalTtHits = 0;
    this.totalTtMisses = 0;
    this.totalBestMoveChanges = 0;
    this.maxDepthSeen = 0;
    this.firstEventTimestamp = 0;
    this.lastEventTimestamp = 0;
  }

  /**
   * Return the raw event log for external analysis.
   */
  getRawEvents(): ReadonlyArray<SearchEvent> {
    return this.events;
  }

  // ── Private ────────────────────────────────────────────────────────

  private increment(map: Map<number, number>, key: number): void {
    map.set(key, (map.get(key) ?? 0) + 1);
  }

  private buildDepthReports(): DepthReport[] {
    const reports: DepthReport[] = [];

    for (let d = 0; d <= this.maxDepthSeen; d++) {
      const nodesVisited = this.depthNodes.get(d) ?? 0;
      if (nodesVisited === 0 && (this.depthPruned.get(d) ?? 0) === 0) {
        continue;
      }

      const startTimestamp = this.depthFirstTimestamp.get(d) ?? 0;
      const endTimestamp = this.depthLastTimestamp.get(d) ?? 0;

      reports.push({
        depth: d,
        nodesVisited,
        nodesPruned: this.depthPruned.get(d) ?? 0,
        ttHits: this.depthTtHits.get(d) ?? 0,
        ttMisses: this.depthTtMisses.get(d) ?? 0,
        bestMoveChanges: this.depthBestMoveChanges.get(d) ?? 0,
        startTimestamp,
        endTimestamp,
        durationMs: endTimestamp - startTimestamp,
      });
    }

    return reports;
  }

  /**
   * Compute the effective branching factor (EBF) using the ratio of
   * nodes at successive depths. The EBF is the geometric mean of
   * depth-to-depth node count ratios.
   *
   * For a tree with branching factor b and depth d, the total nodes
   * are approximately b^d. The EBF is the value of b that best fits
   * the observed data.
   */
  private computeEffectiveBranchingFactor(): number {
    const depthCounts: number[] = [];

    for (let d = 0; d <= this.maxDepthSeen; d++) {
      const count = this.depthNodes.get(d) ?? 0;
      if (count > 0) {
        depthCounts.push(count);
      }
    }

    if (depthCounts.length < 2) return 0;

    let logSum = 0;
    let ratioCount = 0;

    for (let i = 1; i < depthCounts.length; i++) {
      const prev = depthCounts[i - 1]!;
      const curr = depthCounts[i]!;

      if (prev > 0 && curr > 0) {
        logSum += Math.log(curr / prev);
        ratioCount++;
      }
    }

    if (ratioCount === 0) return 0;

    return Math.exp(logSum / ratioCount);
  }
}
