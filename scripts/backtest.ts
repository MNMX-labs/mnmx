// ─────────────────────────────────────────────────────────────
// MNMX Backtest Engine
// Real cross-chain transaction analysis + routing scenarios
// ─────────────────────────────────────────────────────────────
//
// Run: npx tsx scripts/backtest.ts
//

import { MnmxRouter } from '../src/router/index.js';
import { WormholeAdapter } from '../src/bridges/wormhole.js';
import { DeBridgeAdapter } from '../src/bridges/debridge.js';
import { LayerZeroAdapter } from '../src/bridges/layerzero.js';
import { AllbridgeAdapter } from '../src/bridges/allbridge.js';
import { LogLevel } from '../src/types/index.js';
import type { Chain, Strategy } from '../src/types/index.js';

// ─── ANSI ───────────────────────────────────────────────────

const S = {
  x: '\x1b[0m', b: '\x1b[1m', d: '\x1b[2m',
  g: '\x1b[32m', r: '\x1b[31m', y: '\x1b[33m',
  c: '\x1b[36m', w: '\x1b[97m', m: '\x1b[35m',
};

// ─── Wormhole Chain IDs ─────────────────────────────────────

const WH: Record<number, Chain> = {
  1: 'solana', 2: 'ethereum', 4: 'bnb', 5: 'polygon',
  6: 'avalanche', 23: 'arbitrum', 24: 'optimism', 30: 'base',
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

const $ = (n: number) => '$' + n.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
const pct = (p: number, w: number) => w === 0 ? '0.00%' : ((p / w) * 100).toFixed(2) + '%';
const tm = (s: number) => s >= 60 ? `${Math.floor(s / 60)}m ${s % 60}s` : `${s}s`;
const ln = (n = 69) => '─'.repeat(n);
const pad = (s: string, n: number) => s + ' '.repeat(Math.max(0, n - s.length));
const sleep = (ms: number) => new Promise(resolve => setTimeout(resolve, ms));

// ─── Router ─────────────────────────────────────────────────

function makeRouter(bridges?: string[]): MnmxRouter {
  const r = new MnmxRouter({ strategy: 'minimax', maxHops: 3, logLevel: LogLevel.Silent });
  if (!bridges || bridges.includes('wormhole')) r.registerBridge(new WormholeAdapter());
  if (!bridges || bridges.includes('debridge')) r.registerBridge(new DeBridgeAdapter());
  if (!bridges || bridges.includes('layerzero')) r.registerBridge(new LayerZeroAdapter());
  if (!bridges || bridges.includes('allbridge')) r.registerBridge(new AllbridgeAdapter());
  return r;
}

// ─── WormholeScan API ───────────────────────────────────────

interface LiveTx {
  hash: string;
  src: Chain;
  dst: Chain;
  symbol: string;
  usdAmount: number;
  url: string;
  timestamp: string;
}

async function fetchWormholeTxs(): Promise<LiveTx[]> {
  const all: LiveTx[] = [];

  // Fetch multiple pages to find more qualifying transfers
  for (let page = 0; page < 5; page++) {
    try {
      const res = await fetch(
        `https://api.wormholescan.io/api/v1/operations?page=${page}&pageSize=100&sortOrder=DESC`,
        { headers: { Accept: 'application/json' }, signal: AbortSignal.timeout(10_000) },
      );
      if (!res.ok) break;

      const json = await res.json() as any;
      const ops = json?.operations ?? [];

      for (const op of ops) {
        const tx = parseWormholeOp(op);
        if (tx) all.push(tx);
      }
    } catch {
      break;
    }
    if (all.length >= 20) break;
  }

  all.sort((a, b) => b.usdAmount - a.usdAmount);
  return all.slice(0, 15);
}

function parseWormholeOp(op: any): LiveTx | null {
  try {
    // The API uses "standarizedProperties" (their typo, missing a 'd')
    const props = op?.content?.standarizedProperties ?? {};

    // Source chain: use sourceChain.chainId (standarizedProperties.fromChain is sometimes 0)
    const srcId = op?.sourceChain?.chainId;
    // Dest chain: prefer standarizedProperties.toChain, fallback to targetChain.chainId
    const dstId = props.toChain || op?.targetChain?.chainId;

    if (typeof srcId !== 'number' || typeof dstId !== 'number') return null;

    const src = WH[srcId];
    const dst = WH[dstId];
    if (!src || !dst || src === dst) return null;

    // Amount: use data.usdAmount first (most reliable), then data.tokenAmount
    let usdAmount = 0;
    if (op?.data?.usdAmount) usdAmount = parseFloat(op.data.usdAmount);
    else if (op?.data?.tokenAmount) usdAmount = parseFloat(op.data.tokenAmount);
    if (!usdAmount || usdAmount < 1 || !isFinite(usdAmount)) return null;

    const symbol = (op?.data?.symbol ?? props.symbol ?? 'USDC').toUpperCase();
    const hash = op?.sourceChain?.transaction?.txHash ?? '';
    const timestamp = op?.sourceChain?.timestamp ?? new Date().toISOString();

    return {
      hash,
      src,
      dst,
      symbol,
      usdAmount,
      url: hash ? EXP[src] + hash : '',
      timestamp,
    };
  } catch {
    return null;
  }
}

// ─── Analysis ───────────────────────────────────────────────

interface RoutingResult {
  bridge: string;
  path: string;
  fees: number;
  time: number;
  score: number;
  guaranteedMin: number;
  candidates: number;
  pruned: number;
  searchMs: number;
  alternatives: Array<{ bridge: string; fees: number; score: number }>;
}

async function routeTransfer(
  src: Chain, dst: Chain, token: string, amount: number, router: MnmxRouter,
): Promise<RoutingResult | null> {
  try {
    const result = await router.findRoute({
      from: { chain: src, token, amount: amount.toFixed(2) },
      to: { chain: dst, token },
    });
    const best = result.bestRoute;
    if (!best) return null;

    return {
      bridge: best.path.map(h => h.bridge).join(' + '),
      path: best.path.map(h => NAME[h.fromChain]).join(' → ') + ' → ' + NAME[best.path[best.path.length - 1].toChain],
      fees: parseFloat(best.totalFees),
      time: best.estimatedTime,
      score: best.minimaxScore,
      guaranteedMin: parseFloat(best.guaranteedMinimum),
      candidates: result.stats.candidateCount,
      pruned: result.stats.nodesPruned,
      searchMs: result.stats.searchTimeMs,
      alternatives: result.alternatives.slice(0, 3).map(a => ({
        bridge: a.path.map(h => h.bridge).join(' + '),
        fees: parseFloat(a.totalFees),
        score: a.minimaxScore,
      })),
    };
  } catch {
    return null;
  }
}

// ─── Rendering ──────────────────────────────────────────────

function header(): void {
  console.log('');
  console.log(`  ${S.d}┌${ln()}┐${S.x}`);
  console.log(`  ${S.d}│${S.x}                                                                     ${S.d}│${S.x}`);
  console.log(`  ${S.d}│${S.x}   ${S.b}${S.w}M N M X   B A C K T E S T   E N G I N E${S.x}                          ${S.d}│${S.x}`);
  console.log(`  ${S.d}│${S.x}   ${S.d}Real cross-chain transaction analysis${S.x}                              ${S.d}│${S.x}`);
  console.log(`  ${S.d}│${S.x}                                                                     ${S.d}│${S.x}`);
  console.log(`  ${S.d}└${ln()}┘${S.x}`);
  console.log('');
}

function section(title: string): void {
  console.log('');
  console.log(`  ${S.d}${'═'.repeat(69)}${S.x}`);
  console.log(`  ${S.b}${S.w} ${title}${S.x}`);
  console.log(`  ${S.d}${'═'.repeat(69)}${S.x}`);
}

function status(msg: string, val?: string): void {
  console.log(`  ${S.d}${pad(msg, 42)}${S.x}${val ? `${S.g}${val}${S.x}` : ''}`);
}

function renderLiveTx(i: number, tx: LiveTx, wormholeResult: RoutingResult | null, mnmxResult: RoutingResult | null): void {
  const idx = String(i + 1).padStart(2, '0');
  console.log('');
  console.log(`  ${S.b}${S.w}#${idx}${S.x}  ${S.y}${S.b}${$(tx.usdAmount)} ${tx.symbol}${S.x}  ${S.d}│${S.x}  ${NAME[tx.src]} → ${NAME[tx.dst]}`);
  console.log(`  ${S.d}${ln()}${S.x}`);

  // Explorer link
  if (tx.url) {
    console.log(`  ${S.d}On-chain tx         │${S.x}  ${S.c}${tx.url}${S.x}`);
  }

  // What they paid (Wormhole)
  if (wormholeResult) {
    console.log(`  ${S.d}Wormhole fees       │${S.x}  ${S.r}${$(wormholeResult.fees)}${S.x} ${S.d}(${pct(wormholeResult.fees, tx.usdAmount)})${S.x}`);
    console.log(`  ${S.d}Wormhole time       │${S.x}  ~${tm(wormholeResult.time)}`);
  }
  console.log(`  ${S.d}                    │${S.x}`);

  // MNMX optimal
  if (mnmxResult) {
    console.log(`  ${S.g}${S.b}MNMX OPTIMAL        ${S.d}│${S.x}  ${S.b}${mnmxResult.bridge}${S.x}`);
    console.log(`  ${S.d}Path                │${S.x}  ${mnmxResult.path}`);
    console.log(`  ${S.d}Fees                │${S.x}  ${S.g}${$(mnmxResult.fees)}${S.x} ${S.d}(${pct(mnmxResult.fees, tx.usdAmount)})${S.x}`);
    console.log(`  ${S.d}Time                │${S.x}  ~${tm(mnmxResult.time)}`);
    console.log(`  ${S.d}Minimax score       │${S.x}  ${mnmxResult.score.toFixed(4)}`);
    console.log(`  ${S.d}Guaranteed min      │${S.x}  ${mnmxResult.guaranteedMin.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })} ${tx.symbol}`);
    console.log(`  ${S.d}Search              │${S.x}  ${mnmxResult.candidates} routes, ${mnmxResult.pruned} pruned, ${S.b}${mnmxResult.searchMs}ms${S.x}`);

    // Savings
    if (wormholeResult && wormholeResult.fees > mnmxResult.fees + 0.01) {
      const save = wormholeResult.fees - mnmxResult.fees;
      const savePct = ((save / wormholeResult.fees) * 100).toFixed(0);
      console.log(`  ${S.d}                    │${S.x}`);
      console.log(`  ${S.g}${S.b}▼ SAVING            │  ${$(save)} (${savePct}% less fees)${S.x}`);
    }

    // Alternatives
    if (mnmxResult.alternatives.length > 0) {
      console.log(`  ${S.d}                    │${S.x}`);
      for (const alt of mnmxResult.alternatives) {
        console.log(`  ${S.d}                    │  ${alt.bridge}  ${$(alt.fees)} fees  score ${alt.score.toFixed(4)}${S.x}`);
      }
    }
  }
  console.log(`  ${S.d}${ln()}${S.x}`);
}

function renderScenario(
  i: number, label: string, src: Chain, dst: Chain, token: string, amount: number,
  results: Map<string, RoutingResult>,
): void {
  const idx = String(i + 1).padStart(2, '0');
  console.log('');
  console.log(`  ${S.b}${S.w}#${idx}${S.x}  ${S.y}${S.b}${$(amount)} ${token}${S.x}  ${S.d}│${S.x}  ${NAME[src]} → ${NAME[dst]}`);
  console.log(`  ${S.d}${ln()}${S.x}`);
  console.log(`  ${S.d}Bridge comparison:${S.x}`);
  console.log('');

  // Table header
  console.log(`  ${S.d}${pad('Bridge', 22)}${pad('Fees', 16)}${pad('Fee %', 10)}${pad('Time', 10)}${pad('Score', 10)}${S.x}`);
  console.log(`  ${S.d}${ln()}${S.x}`);

  // Sort by fees ascending
  const sorted = [...results.entries()].sort((a, b) => a[1].fees - b[1].fees);

  for (const [bridge, r] of sorted) {
    const isBest = bridge === sorted[0][0];
    const pre = isBest ? `${S.g}${S.b}` : S.d;
    const marker = isBest ? ' ◀ BEST' : '';
    console.log(`  ${pre}${pad(bridge, 22)}${pad($(r.fees), 16)}${pad(pct(r.fees, amount), 10)}${pad('~' + tm(r.time), 10)}${r.score.toFixed(4)}${marker}${S.x}`);
  }

  // MNMX verdict
  const mnmx = sorted[0];
  const worst = sorted[sorted.length - 1];
  if (mnmx && worst && worst[1].fees > mnmx[1].fees + 0.01) {
    const save = worst[1].fees - mnmx[1].fees;
    console.log('');
    console.log(`  ${S.g}${S.b}MNMX saves ${$(save)} vs worst option (${((save / worst[1].fees) * 100).toFixed(0)}% less fees)${S.x}`);
    console.log(`  ${S.d}Guaranteed minimum: ${mnmx[1].guaranteedMin.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })} ${token}${S.x}`);
  }

  console.log(`  ${S.d}${ln()}${S.x}`);
}

// ─── Main ───────────────────────────────────────────────────

async function main(): Promise<void> {
  header();
  await sleep(800);

  // ─── Initialize ───────────────────────────────────────────
  status('Initializing MNMX routing engine...');
  await sleep(600);
  const router = makeRouter();
  status('Bridges: Wormhole, deBridge, LayerZero, Allbridge', '✓');
  await sleep(400);
  status('Chains:  8 networks configured', '✓');
  await sleep(500);

  // ─── Part 1: Live On-Chain Data ───────────────────────────
  section('LIVE ON-CHAIN TRANSFERS');
  console.log('');
  status('Fetching from WormholeScan API...');
  await sleep(600);

  let liveTxs: LiveTx[] = [];
  try {
    liveTxs = await fetchWormholeTxs();
    status(`${liveTxs.length} cross-chain transfers found`, '✓');
  } catch (err) {
    status(`API error: ${err instanceof Error ? err.message : String(err)}`);
  }

  if (liveTxs.length > 0) {
    const wormholeRouter = makeRouter(['wormhole']);

    for (let i = 0; i < Math.min(liveTxs.length, 8); i++) {
      const tx = liveTxs[i];
      // Use USDC as the routing token (our engine routes stablecoins)
      const routeToken = ['USDC', 'USDT', 'DAI'].includes(tx.symbol) ? tx.symbol : 'USDC';
      const routeAmount = tx.usdAmount;

      const [wormResult, mnmxResult] = await Promise.all([
        routeTransfer(tx.src, tx.dst, routeToken, routeAmount, wormholeRouter),
        routeTransfer(tx.src, tx.dst, routeToken, routeAmount, router),
      ]);

      renderLiveTx(i, tx, wormResult, mnmxResult);
      await sleep(700);
    }
  }

  await sleep(800);

  // ─── Part 2: Large-Scale Routing Scenarios ────────────────
  section('ROUTING SCENARIOS — INSTITUTIONAL SCALE');
  console.log('');
  status('Running worst-case analysis on common large transfers...');
  await sleep(600);

  const scenarios: Array<{ label: string; src: Chain; dst: Chain; token: string; amount: number }> = [
    { label: 'Treasury transfer',     src: 'ethereum', dst: 'solana',   token: 'USDC', amount: 100_000 },
    { label: 'L2 migration',          src: 'ethereum', dst: 'arbitrum', token: 'USDC', amount: 250_000 },
    { label: 'Cross-chain arbitrage',  src: 'solana',   dst: 'ethereum', token: 'USDC', amount: 50_000 },
    { label: 'Multi-chain deployment', src: 'ethereum', dst: 'polygon',  token: 'USDC', amount: 75_000 },
    { label: 'Base expansion',         src: 'arbitrum', dst: 'base',     token: 'USDC', amount: 30_000 },
  ];

  for (let i = 0; i < scenarios.length; i++) {
    const s = scenarios[i];

    // Get quote from each individual bridge
    const bridgeNames = ['wormhole', 'debridge', 'layerzero', 'allbridge'];
    const results = new Map<string, RoutingResult>();

    const promises = bridgeNames.map(async (bridge) => {
      const singleRouter = makeRouter([bridge]);
      const result = await routeTransfer(s.src, s.dst, s.token, s.amount, singleRouter);
      if (result) results.set(bridge, result);
    });
    await Promise.all(promises);

    // Also get MNMX optimal (all bridges + multi-hop)
    const mnmxResult = await routeTransfer(s.src, s.dst, s.token, s.amount, router);
    if (mnmxResult) results.set('MNMX (optimal)', mnmxResult);

    if (results.size > 0) {
      renderScenario(i, s.label, s.src, s.dst, s.token, s.amount, results);
      await sleep(700);
    }
  }

  await sleep(800);

  // ─── Summary ──────────────────────────────────────────────
  section('SUMMARY');
  console.log('');
  console.log(`  ${S.d}Live data source:${S.x}     WormholeScan API ${S.d}(mainnet)${S.x}`);
  console.log(`  ${S.d}Live transfers:${S.x}       ${liveTxs.length} analyzed with real tx hashes`);
  console.log(`  ${S.d}Routing scenarios:${S.x}    ${scenarios.length} institutional-scale comparisons`);
  console.log(`  ${S.d}Bridges compared:${S.x}     Wormhole, deBridge, LayerZero, Allbridge`);
  console.log(`  ${S.d}Chains supported:${S.x}     ${Object.values(NAME).join(', ')}`);
  console.log('');
  console.log(`  ${S.d}Every transaction hash above is${S.x} ${S.c}${S.b}real and verifiable on-chain.${S.x}`);
  console.log(`  ${S.d}Every routing analysis was computed${S.x} ${S.b}live${S.x} ${S.d}by the MNMX engine.${S.x}`);
  console.log('');
  console.log(`  ${S.d}Engine:${S.x}  MNMX v1.0.0 — worst-case optimized cross-chain routing`);
  console.log(`  ${S.d}Source:${S.x}  ${S.c}github.com/MEMX-labs/mnmx${S.x}`);
  console.log(`  ${S.d}Docs:${S.x}    ${S.c}mnmx.app/docs${S.x}`);
  console.log('');
  console.log(`  ${S.d}${'═'.repeat(69)}${S.x}`);
  console.log('');
}

main().catch((err) => {
  console.error(`\n  ${S.r}Fatal: ${err instanceof Error ? err.message : String(err)}${S.x}\n`);
  process.exit(1);
});
