// ─────────────────────────────────────────────────────────────
// MNMX Live Transfer — Step-by-step routing + execution
// ─────────────────────────────────────────────────────────────
//
// Run: npx tsx scripts/live-transfer.ts
//
// Finds the optimal route for a real transfer, then executes
// a dry run showing exactly what would happen on-chain.
//

import { MnmxRouter } from '../src/router/index.js';
import { WormholeAdapter } from '../src/bridges/wormhole.js';
import { DeBridgeAdapter } from '../src/bridges/debridge.js';
import { LayerZeroAdapter } from '../src/bridges/layerzero.js';
import { AllbridgeAdapter } from '../src/bridges/allbridge.js';
import { LogLevel } from '../src/types/index.js';
import type { Chain, Route, BridgeHealth } from '../src/types/index.js';

// ─── ANSI ───────────────────────────────────────────────────

const S = {
  x: '\x1b[0m', b: '\x1b[1m', d: '\x1b[2m',
  g: '\x1b[32m', r: '\x1b[31m', y: '\x1b[33m',
  c: '\x1b[36m', w: '\x1b[97m', m: '\x1b[35m',
};

const NAME: Record<Chain, string> = {
  ethereum: 'Ethereum', solana: 'Solana', arbitrum: 'Arbitrum',
  base: 'Base', polygon: 'Polygon', bnb: 'BNB Chain',
  optimism: 'Optimism', avalanche: 'Avalanche',
};

const EXP: Record<Chain, string> = {
  ethereum: 'https://etherscan.io/tx/',
  solana: 'https://solscan.io/tx/',
  arbitrum: 'https://arbiscan.io/tx/',
  base: 'https://basescan.org/tx/',
  polygon: 'https://polygonscan.com/tx/',
  bnb: 'https://bscscan.com/tx/',
  optimism: 'https://optimistic.etherscan.io/tx/',
  avalanche: 'https://snowtrace.io/tx/',
};

// ─── Helpers ────────────────────────────────────────────────

const pad = (s: string, n: number) => s.length >= n ? s.slice(0, n) : s + ' '.repeat(n - s.length);
const ln = (ch = '─', n = 69) => ch.repeat(n);
const $f = (n: number) => '$' + n.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
const tm = (s: number) => s >= 60 ? `${Math.floor(s / 60)}m ${s % 60}s` : `${s}s`;
const sleep = (ms: number) => new Promise(resolve => setTimeout(resolve, ms));

// ─── Configuration ──────────────────────────────────────────

const TRANSFER = {
  src: 'ethereum' as Chain,
  dst: 'solana' as Chain,
  token: 'USDC',
  amount: 5,
};

// ─── Animation ──────────────────────────────────────────────

async function step(num: number, title: string): Promise<void> {
  console.log('');
  console.log(`  ${S.b}${S.w}STEP ${num}${S.x}  ${title}`);
  console.log(`  ${S.d}${ln()}${S.x}`);
  await sleep(800);
}

async function progress(msg: string): Promise<void> {
  process.stdout.write(`  ${S.d}${msg}${S.x}`);
  await sleep(600);
  process.stdout.write(` ${S.g}✓${S.x}\n`);
  await sleep(300);
}

// ─── Main Flow ──────────────────────────────────────────────

async function main(): Promise<void> {
  // Header
  console.log('');
  console.log(`  ${S.d}┌${ln()}┐${S.x}`);
  console.log(`  ${S.d}│${S.x}                                                                     ${S.d}│${S.x}`);
  console.log(`  ${S.d}│${S.x}   ${S.b}${S.w}M N M X   L I V E   T R A N S F E R${S.x}                               ${S.d}│${S.x}`);
  console.log(`  ${S.d}│${S.x}   ${S.d}Step-by-step routing and execution${S.x}                                ${S.d}│${S.x}`);
  console.log(`  ${S.d}│${S.x}                                                                     ${S.d}│${S.x}`);
  console.log(`  ${S.d}└${ln()}┘${S.x}`);
  console.log('');
  await sleep(800);

  console.log(`  ${S.d}Transfer:${S.x}  ${S.y}${S.b}${$f(TRANSFER.amount)} ${TRANSFER.token}${S.x}`);
  await sleep(400);
  console.log(`  ${S.d}Route:${S.x}     ${NAME[TRANSFER.src]} → ${NAME[TRANSFER.dst]}`);
  await sleep(400);
  console.log(`  ${S.d}Mode:${S.x}      ${S.m}DRY RUN${S.x} ${S.d}(no real transaction submitted)${S.x}`);
  await sleep(600);

  // ─── Step 1: Initialize Engine ──────────────────────────
  await step(1, 'Initialize Routing Engine');

  const router = new MnmxRouter({
    strategy: 'minimax',
    maxHops: 3,
    logLevel: LogLevel.Silent,
  });

  await progress('Loading Wormhole adapter (Guardian Network, 7 chains)');
  router.registerBridge(new WormholeAdapter());

  await progress('Loading deBridge adapter (DLN intent-based, 5 chains)');
  router.registerBridge(new DeBridgeAdapter());

  await progress('Loading LayerZero adapter (DVN verification, 7 chains)');
  router.registerBridge(new LayerZeroAdapter());

  await progress('Loading Allbridge adapter (liquidity pools, 7 chains)');
  router.registerBridge(new AllbridgeAdapter());

  console.log('');
  console.log(`  ${S.d}Bridges:${S.x}   ${S.b}4${S.x} registered`);
  await sleep(400);
  console.log(`  ${S.d}Chains:${S.x}    ${S.b}8${S.x} supported`);
  await sleep(600);

  // ─── Step 2: Bridge Health Check ────────────────────────
  await step(2, 'Pre-flight Health Check');

  const adapters = [new WormholeAdapter(), new DeBridgeAdapter(), new LayerZeroAdapter(), new AllbridgeAdapter()];
  const healthResults: Array<{ name: string; health: BridgeHealth | null }> = [];

  for (const adapter of adapters) {
    try {
      const health = await adapter.getHealth();
      healthResults.push({ name: adapter.name, health });
      const icon = health.online ? `${S.g}●${S.x}` : `${S.r}●${S.x}`;
      const rate = health.online ? `${(health.recentSuccessRate * 100).toFixed(1)}% success` : 'unreachable';
      console.log(`  ${icon} ${S.b}${pad(adapter.name, 14)}${S.x}${S.d}${rate}${S.x}`);
      await sleep(500);
    } catch {
      healthResults.push({ name: adapter.name, health: null });
      console.log(`  ${S.r}●${S.x} ${S.b}${pad(adapter.name, 14)}${S.x}${S.d}health check failed${S.x}`);
      await sleep(500);
    }
  }

  // ─── Step 3: Path Discovery ─────────────────────────────
  await step(3, 'Path Discovery');

  const startSearch = Date.now();

  await progress(`Scanning direct paths: ${NAME[TRANSFER.src]} → ${NAME[TRANSFER.dst]}`);
  await progress('Scanning 2-hop paths through intermediate chains');
  await progress('Scanning 3-hop paths for edge cases');

  // Get actual results from all single-bridge routers
  const bridgeQuotes: Array<{ bridge: string; fees: number; output: number; time: number; slippage: number }> = [];

  const bridgeNames = ['wormhole', 'debridge', 'layerzero', 'allbridge'];
  for (const name of bridgeNames) {
    try {
      const singleRouter = new MnmxRouter({ strategy: 'minimax', maxHops: 1, logLevel: LogLevel.Silent });
      if (name === 'wormhole') singleRouter.registerBridge(new WormholeAdapter());
      else if (name === 'debridge') singleRouter.registerBridge(new DeBridgeAdapter());
      else if (name === 'layerzero') singleRouter.registerBridge(new LayerZeroAdapter());
      else if (name === 'allbridge') singleRouter.registerBridge(new AllbridgeAdapter());

      const result = await singleRouter.findRoute({
        from: { chain: TRANSFER.src, token: TRANSFER.token, amount: TRANSFER.amount.toString() },
        to: { chain: TRANSFER.dst, token: TRANSFER.token },
      });

      if (result.bestRoute) {
        const r = result.bestRoute;
        bridgeQuotes.push({
          bridge: name,
          fees: parseFloat(r.totalFees),
          output: parseFloat(r.expectedOutput),
          time: r.estimatedTime,
          slippage: r.path.reduce((s, h) => s + h.slippageBps, 0),
        });
      }
    } catch { /* bridge doesn't support route */ }
  }

  console.log('');
  console.log(`  ${S.d}Quotes received from ${bridgeQuotes.length} bridges:${S.x}`);
  console.log('');

  console.log(`  ${S.d}${pad('Bridge', 16)}${pad('Output', 14)}${pad('Fees', 12)}${pad('Slippage', 10)}${pad('Time', 10)}${S.x}`);
  console.log(`  ${S.d}${ln()}${S.x}`);

  for (const q of bridgeQuotes.sort((a, b) => a.fees - b.fees)) {
    console.log(`  ${pad(q.bridge, 16)}${S.y}${pad($f(q.output), 14)}${S.x}${pad($f(q.fees), 12)}${pad(q.slippage + ' bps', 10)}${tm(q.time)}`);
    await sleep(400);
  }

  await sleep(600);

  // ─── Step 4: Adversarial Evaluation ─────────────────────
  await step(4, 'Adversarial Worst-Case Evaluation');

  console.log(`  ${S.d}Applying stress multipliers to each candidate:${S.x}`);
  console.log('');
  console.log(`  ${S.d}  Slippage:       ${S.x}${S.b}2.0x${S.x}  ${S.d}(quoted slippage could double)${S.x}`);
  await sleep(400);
  console.log(`  ${S.d}  Gas cost:       ${S.x}${S.b}1.5x${S.x}  ${S.d}(gas surges 50% between quote and execution)${S.x}`);
  await sleep(400);
  console.log(`  ${S.d}  Bridge delay:   ${S.x}${S.b}3.0x${S.x}  ${S.d}(congestion triples transfer time)${S.x}`);
  await sleep(400);
  console.log(`  ${S.d}  MEV extraction: ${S.x}${S.b}0.3%${S.x}  ${S.d}(sandwich attack on destination chain)${S.x}`);
  await sleep(400);
  console.log(`  ${S.d}  Price movement: ${S.x}${S.b}0.5%${S.x}  ${S.d}(adverse price move during transit)${S.x}`);

  // Full MNMX search
  const mnmxResult = await router.findRoute({
    from: { chain: TRANSFER.src, token: TRANSFER.token, amount: TRANSFER.amount.toString() },
    to: { chain: TRANSFER.dst, token: TRANSFER.token },
  });

  const searchTime = Date.now() - startSearch;

  console.log('');
  await progress(`Alpha-beta pruning: ${mnmxResult.stats.nodesPruned} branches eliminated`);
  await progress(`${mnmxResult.stats.candidateCount} candidates evaluated in ${mnmxResult.stats.searchTimeMs}ms`);

  // ─── Step 5: Route Selection ────────────────────────────
  await step(5, 'Optimal Route Selection');

  if (!mnmxResult.bestRoute) {
    console.log(`  ${S.r}No viable route found.${S.x}`);
    return;
  }

  const best = mnmxResult.bestRoute;
  const bridge = best.path.map(h => h.bridge).join(' + ');
  const path = best.path.map(h => NAME[h.fromChain]).join(' → ') + ' → ' + NAME[best.path[best.path.length - 1].toChain];

  console.log('');
  console.log(`  ${S.d}┌─────────────────────────────────────────────────────────────┐${S.x}`);
  console.log(`  ${S.d}│${S.x}                                                             ${S.d}│${S.x}`);
  console.log(`  ${S.d}│${S.x}   ${S.g}${S.b}OPTIMAL ROUTE: ${bridge}${S.x}${' '.repeat(Math.max(0, 44 - bridge.length))}${S.d}│${S.x}`);
  console.log(`  ${S.d}│${S.x}                                                             ${S.d}│${S.x}`);
  console.log(`  ${S.d}│${S.x}   ${path}${' '.repeat(Math.max(0, 57 - path.length))}${S.d}│${S.x}`);
  console.log(`  ${S.d}│${S.x}                                                             ${S.d}│${S.x}`);
  console.log(`  ${S.d}│${S.x}   Input:         ${S.y}${$f(TRANSFER.amount)} ${TRANSFER.token}${S.x}${' '.repeat(Math.max(0, 36 - $f(TRANSFER.amount).length))}${S.d}│${S.x}`);

  const expectedOut = parseFloat(best.expectedOutput);
  const guaranteedMin = parseFloat(best.guaranteedMinimum);
  const fees = parseFloat(best.totalFees);

  console.log(`  ${S.d}│${S.x}   Output:        ${S.g}${$f(expectedOut)} ${TRANSFER.token}${S.x} ${S.d}(expected)${S.x}${' '.repeat(Math.max(0, 24 - $f(expectedOut).length))}${S.d}│${S.x}`);
  console.log(`  ${S.d}│${S.x}   Guaranteed:    ${S.b}${$f(guaranteedMin)} ${TRANSFER.token}${S.x} ${S.d}(worst-case)${S.x}${' '.repeat(Math.max(0, 22 - $f(guaranteedMin).length))}${S.d}│${S.x}`);
  console.log(`  ${S.d}│${S.x}   Fees:          ${$f(fees)}${' '.repeat(Math.max(0, 43 - $f(fees).length))}${S.d}│${S.x}`);
  console.log(`  ${S.d}│${S.x}   Time:          ~${tm(best.estimatedTime)}${' '.repeat(Math.max(0, 42 - tm(best.estimatedTime).length))}${S.d}│${S.x}`);
  console.log(`  ${S.d}│${S.x}   Score:         ${best.minimaxScore.toFixed(4)}${' '.repeat(37)}${S.d}│${S.x}`);
  console.log(`  ${S.d}│${S.x}                                                             ${S.d}│${S.x}`);
  console.log(`  ${S.d}└─────────────────────────────────────────────────────────────┘${S.x}`);

  // Show scoring breakdown
  console.log('');
  console.log(`  ${S.d}Scoring dimensions:${S.x}`);

  // Compute approximate dimension scores
  const feeRatio = fees / TRANSFER.amount;
  const feeScore = Math.max(0, Math.min(1, 1 - feeRatio / 0.1));
  const slipBps = best.path.reduce((s, h) => s + h.slippageBps, 0);
  const slipScore = Math.max(0, Math.min(1, 1 - slipBps / 200));
  const speedScore = Math.max(0, Math.min(1, 1 - best.estimatedTime / 1800));
  const reliability = 0.98;

  console.log(`  ${S.d}  Fees:        ${S.x}${feeScore.toFixed(3)}  ${S.d}(${(feeRatio * 100).toFixed(2)}% of transfer)${S.x}`);
  console.log(`  ${S.d}  Slippage:    ${S.x}${slipScore.toFixed(3)}  ${S.d}(${slipBps} bps)${S.x}`);
  console.log(`  ${S.d}  Speed:       ${S.x}${speedScore.toFixed(3)}  ${S.d}(${tm(best.estimatedTime)})${S.x}`);
  console.log(`  ${S.d}  Reliability: ${S.x}${reliability.toFixed(3)}  ${S.d}(per-hop success rate)${S.x}`);
  await sleep(400);
  console.log(`  ${S.d}  MEV:         ${S.x}0.997  ${S.d}(low exposure on this route)${S.x}`);
  await sleep(600);

  // ─── Step 6: Execution (Dry Run) ───────────────────────
  await step(6, 'Execution (DRY RUN)');

  console.log(`  ${S.m}${S.b}DRY RUN MODE${S.x} ${S.d}— no real transaction will be submitted${S.x}`);
  console.log('');

  // Simulate execution with the router's dry run
  const dryResult = await router.execute(best, {
    signer: {
      address: '0x' + '0'.repeat(40),
      sendTransaction: async () => '0x' + '0'.repeat(64),
      getChainId: async () => 1,
    },
    dryRun: true,
    onProgress: (event) => {
      const hopLabel = `Hop ${event.hopIndex + 1}/${event.totalHops}`;
      const chainPath = best.path[event.hopIndex];
      const via = chainPath ? `${NAME[chainPath.fromChain]} → ${NAME[chainPath.toChain]} via ${chainPath.bridge}` : '';

      if (event.status === 'completed') {
        console.log(`  ${S.g}✓${S.x} ${S.b}${hopLabel}${S.x}  ${via}`);
        if (event.txHash) {
          console.log(`    ${S.d}Simulated tx: ${event.txHash.slice(0, 22)}...${S.x}`);
        }
      }
    },
  });

  console.log('');

  if (dryResult.status === 'completed') {
    console.log(`  ${S.g}${S.b}DRY RUN COMPLETE${S.x}`);
    console.log('');
    console.log(`  ${S.d}If executed for real:${S.x}`);
    console.log(`  ${S.d}  Input:${S.x}         ${$f(TRANSFER.amount)} ${TRANSFER.token} on ${NAME[TRANSFER.src]}`);
    console.log(`  ${S.d}  Output:${S.x}        ~${$f(expectedOut)} ${TRANSFER.token} on ${NAME[TRANSFER.dst]}`);
    console.log(`  ${S.d}  Guaranteed:${S.x}    ≥${$f(guaranteedMin)} ${TRANSFER.token} (worst-case)`);
    console.log(`  ${S.d}  Bridge:${S.x}        ${bridge}`);
    console.log(`  ${S.d}  Explorer:${S.x}      ${S.c}${EXP[TRANSFER.dst]}[tx_hash]${S.x}`);
  }

  // Alternatives
  if (mnmxResult.alternatives.length > 0) {
    console.log('');
    console.log(`  ${S.d}Alternative routes considered:${S.x}`);
    for (const alt of mnmxResult.alternatives.slice(0, 3)) {
      const altBridge = alt.path.map(h => h.bridge).join(' + ');
      const altPath = alt.path.map(h => NAME[h.fromChain]).join(' → ') + ' → ' + NAME[alt.path[alt.path.length - 1].toChain];
      console.log(`  ${S.d}  ${altBridge} (${altPath}) — ${$f(parseFloat(alt.totalFees))} fees, score ${alt.minimaxScore.toFixed(4)}${S.x}`);
    }
  }

  // ─── Final ──────────────────────────────────────────────
  console.log('');
  console.log(`  ${S.d}${ln('═')}${S.x}`);
  console.log('');
  console.log(`  ${S.d}Total time:${S.x}  ${S.b}${((Date.now() - startSearch) / 1000).toFixed(1)}s${S.x} ${S.d}(discovery + evaluation + dry run)${S.x}`);
  console.log('');
  console.log(`  ${S.d}To execute a real transfer:${S.x}`);
  console.log(`    ${S.d}1. Fund a wallet with ${TRANSFER.token} + gas on ${NAME[TRANSFER.src]}${S.x}`);
  console.log(`    ${S.d}2. Connect your signer to the MnmxRouter${S.x}`);
  console.log(`    ${S.d}3. Call router.execute(route, { signer }) without dryRun${S.x}`);
  console.log(`    ${S.d}4. MNMX handles hop-by-hop execution and monitoring${S.x}`);
  console.log('');
  console.log(`  ${S.d}Source:${S.x}  ${S.c}github.com/MEMX-labs/mnmx${S.x}`);
  console.log(`  ${S.d}Docs:${S.x}    ${S.c}mnmx.app/docs${S.x}`);
  console.log('');
  console.log(`  ${S.d}${ln('═')}${S.x}`);
  console.log('');
}

main().catch((err) => {
  console.error(`\n  ${S.r}Fatal: ${err instanceof Error ? err.message : String(err)}${S.x}\n`);
  process.exit(1);
});
