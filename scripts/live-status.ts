// ─────────────────────────────────────────────────────────────
// MNMX Live Status — Bridge Infrastructure Monitor
// Queries real bridge APIs in real-time
// ─────────────────────────────────────────────────────────────
//
// Run: npx tsx scripts/live-status.ts
//

import { MnmxRouter } from '../src/router/index.js';
import { WormholeAdapter } from '../src/bridges/wormhole.js';
import { DeBridgeAdapter } from '../src/bridges/debridge.js';
import { LayerZeroAdapter } from '../src/bridges/layerzero.js';
import { AllbridgeAdapter } from '../src/bridges/allbridge.js';
import { LogLevel } from '../src/types/index.js';
import type { Chain, BridgeHealth } from '../src/types/index.js';

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

// ─── Helpers ────────────────────────────────────────────────

const pad = (s: string, n: number) => s.length >= n ? s.slice(0, n) : s + ' '.repeat(n - s.length);
const ln = (ch = '─', n = 69) => ch.repeat(n);
const $ = (n: number) => '$' + n.toLocaleString('en-US', { maximumFractionDigits: 0 });
const $f = (n: number) => '$' + n.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
const sleep = (ms: number) => new Promise(resolve => setTimeout(resolve, ms));
const bar = (ratio: number, width = 20) => {
  const filled = Math.round(ratio * width);
  return '▓'.repeat(filled) + '░'.repeat(width - filled);
};

function header(): void {
  console.log('');
  console.log(`  ${S.d}┌${ln()}┐${S.x}`);
  console.log(`  ${S.d}│${S.x}                                                                     ${S.d}│${S.x}`);
  console.log(`  ${S.d}│${S.x}   ${S.b}${S.w}M N M X   L I V E   S T A T U S${S.x}                                   ${S.d}│${S.x}`);
  console.log(`  ${S.d}│${S.x}   ${S.d}Bridge infrastructure monitor — all data queried in real-time${S.x}      ${S.d}│${S.x}`);
  console.log(`  ${S.d}│${S.x}                                                                     ${S.d}│${S.x}`);
  console.log(`  ${S.d}└${ln()}┘${S.x}`);
  console.log('');
}

function section(title: string): void {
  console.log('');
  console.log(`  ${S.d}${ln('═')}${S.x}`);
  console.log(`  ${S.b}${S.w} ${title}${S.x}`);
  console.log(`  ${S.d}${ln('═')}${S.x}`);
}

function kv(key: string, value: string, indent = 2): void {
  console.log(`${' '.repeat(indent)}  ${S.d}${pad(key + ':', 24)}${S.x}${value}`);
}

// ─── Bridge Health ──────────────────────────────────────────

async function queryBridgeHealth(): Promise<void> {
  section('BRIDGE HEALTH STATUS');
  console.log('');
  console.log(`  ${S.d}Querying health endpoints on all 4 bridges...${S.x}`);
  console.log('');

  const adapters = [
    new WormholeAdapter(),
    new DeBridgeAdapter(),
    new LayerZeroAdapter(),
    new AllbridgeAdapter(),
  ];

  // Table header
  console.log(`  ${S.d}${pad('Bridge', 16)}${pad('Status', 12)}${pad('Success', 12)}${pad('Congestion', 24)}${pad('Confirm', 10)}${S.x}`);
  console.log(`  ${S.d}${ln()}${S.x}`);

  for (const adapter of adapters) {
    try {
      const health: BridgeHealth = await adapter.getHealth();
      const statusIcon = health.online ? `${S.g}● ONLINE${S.x}` : `${S.r}● DOWN${S.x}`;
      const successStr = health.online ? `${(health.recentSuccessRate * 100).toFixed(1)}%` : '—';
      const congBar = health.online ? `${bar(health.congestion, 15)} ${(health.congestion * 100).toFixed(0)}%` : '—';
      const confirmStr = health.online ? `${health.medianConfirmTime}s` : '—';

      console.log(`  ${S.b}${pad(adapter.name, 16)}${S.x}${pad('', 0)}${statusIcon}${' '.repeat(Math.max(0, 4 - (health.online ? 0 : 2)))}${pad(successStr, 12)}${pad(congBar, 24)}${confirmStr}`);
    } catch {
      console.log(`  ${S.b}${pad(adapter.name, 16)}${S.x}${S.r}● ERROR${S.x}    ${S.d}—${S.x}`);
    }
  }
  console.log('');
  console.log(`  ${S.d}Source: Real-time API calls to each bridge's monitoring endpoint${S.x}`);
}

// ─── Wormhole Network Stats ────────────────────────────────

async function queryWormholeNetwork(): Promise<void> {
  section('WORMHOLE NETWORK — LIVE DATA');
  console.log('');
  console.log(`  ${S.d}Source: ${S.c}api.wormholescan.io${S.x}`);
  console.log('');

  try {
    // Scorecards
    const [scoreRes, txRes] = await Promise.all([
      fetch('https://api.wormholescan.io/api/v1/scorecards', { signal: AbortSignal.timeout(10_000) }),
      fetch('https://api.wormholescan.io/api/v1/last-txs', { signal: AbortSignal.timeout(10_000) }),
    ]);

    if (scoreRes.ok) {
      const scores = await scoreRes.json() as any;

      kv('24h Messages', `${S.b}${parseInt(scores['24h_messages']).toLocaleString()}${S.x}`);
      kv('24h Volume', `${S.y}${S.b}${$(parseFloat(scores['24h_volume']))}${S.x}`);
      kv('7d Volume', `${S.y}${$(parseFloat(scores['7d_volume']))}${S.x}`);
      kv('30d Volume', `${S.y}${$(parseFloat(scores['30d_volume']))}${S.x}`);
      kv('Total Volume', `${S.y}${S.b}${$(parseFloat(scores.total_volume))}${S.x}`);
      kv('TVL', `${S.g}${S.b}${$(parseFloat(scores.tvl))}${S.x}`);
      kv('Total Tx Count', parseInt(scores.total_tx_count).toLocaleString());
    }

    // Hourly throughput
    if (txRes.ok) {
      const txData = await txRes.json() as Array<{ time: string; count: number }>;
      const recent = txData.slice(0, 12);
      const maxCount = Math.max(...recent.map(t => t.count), 1);

      console.log('');
      console.log(`  ${S.d}Hourly throughput (last 12h):${S.x}`);
      console.log('');

      for (const entry of recent) {
        const hour = new Date(entry.time).toUTCString().slice(17, 22);
        const barWidth = Math.round((entry.count / maxCount) * 30);
        const barStr = '▓'.repeat(barWidth) + '░'.repeat(30 - barWidth);
        console.log(`  ${S.d}${pad(hour + ' UTC', 12)}${S.x}${S.c}${barStr}${S.x}  ${entry.count}`);
      }
    }
  } catch (err) {
    console.log(`  ${S.r}Failed to fetch: ${err instanceof Error ? err.message : String(err)}${S.x}`);
  }
}

// ─── deBridge DLN Network ──────────────────────────────────

async function queryDeBridgeNetwork(): Promise<void> {
  section('DEBRIDGE DLN NETWORK — LIVE DATA');
  console.log('');
  console.log(`  ${S.d}Source: ${S.c}dln.debridge.finance${S.x}`);
  console.log('');

  try {
    const res = await fetch('https://dln.debridge.finance/v1.0/supported-chains-info', {
      signal: AbortSignal.timeout(10_000),
    });

    if (!res.ok) {
      console.log(`  ${S.r}API returned ${res.status}${S.x}`);
      return;
    }

    const data = await res.json() as { chains: Array<{ chainId: number; chainName: string }> };
    const chains = data.chains || [];

    kv('Total Chains', `${S.b}${chains.length}${S.x}`);
    console.log('');
    console.log(`  ${S.d}Active chains:${S.x}`);

    // Display in rows of 4
    for (let i = 0; i < chains.length; i += 4) {
      const row = chains.slice(i, i + 4).map(c => pad(c.chainName, 16)).join('');
      console.log(`    ${S.d}${row}${S.x}`);
    }

    console.log('');
    console.log(`  ${S.d}DLN (Debridge Liquidity Network) uses intent-based order fills.${S.x}`);
    console.log(`  ${S.d}Takers compete to fill cross-chain orders at the best price.${S.x}`);
  } catch (err) {
    console.log(`  ${S.r}Failed to fetch: ${err instanceof Error ? err.message : String(err)}${S.x}`);
  }
}

// ─── Allbridge Core Liquidity ──────────────────────────────

async function queryAllbridgePools(): Promise<void> {
  section('ALLBRIDGE CORE — LIVE LIQUIDITY POOLS');
  console.log('');
  console.log(`  ${S.d}Source: ${S.c}core.api.allbridgecoreapi.net${S.x}`);
  console.log('');

  try {
    const res = await fetch('https://core.api.allbridgecoreapi.net/token-info', {
      signal: AbortSignal.timeout(10_000),
    });

    if (!res.ok) {
      console.log(`  ${S.r}API returned ${res.status}${S.x}`);
      return;
    }

    const data = await res.json() as Record<string, { tokens: any[] }>;

    // Map Allbridge chain keys to our chain names
    const chainMap: Record<string, string> = {
      ETH: 'Ethereum', SOL: 'Solana', ARB: 'Arbitrum', BSC: 'BNB Chain',
      POL: 'Polygon', AVA: 'Avalanche', OPT: 'Optimism', BAS: 'Base',
      TRX: 'Tron', SRB: 'Stellar', CEL: 'Celo',
    };

    let totalTVL = 0;
    const pools: Array<{ chain: string; symbol: string; balance: number; apr: number; fee: string }> = [];

    for (const [key, chain] of Object.entries(data)) {
      const chainName = chainMap[key] || key;
      if (!chain.tokens) continue;

      for (const token of chain.tokens) {
        if (!token.poolInfo) continue;
        const decimals = token.decimals || 6;
        const balance = parseInt(token.poolInfo.tokenBalance || '0') / (10 ** decimals);
        const apr = parseFloat(token.apr || '0') * 100;
        const fee = token.feeShare || '0';

        if (balance > 0) {
          totalTVL += balance;
          pools.push({ chain: chainName, symbol: token.symbol, balance, apr, fee });
        }
      }
    }

    // Sort by balance descending
    pools.sort((a, b) => b.balance - a.balance);

    kv('Total Pools', `${S.b}${pools.length}${S.x}`);
    kv('Total TVL', `${S.g}${S.b}${$(totalTVL)}${S.x}`);
    console.log('');

    // Table header
    console.log(`  ${S.d}${pad('Chain', 14)}${pad('Token', 8)}${pad('Pool Balance', 18)}${pad('APR', 10)}${pad('Fee', 8)}${S.x}`);
    console.log(`  ${S.d}${ln()}${S.x}`);

    // Show top 15 pools
    for (const pool of pools.slice(0, 15)) {
      const balStr = $(pool.balance);
      const aprStr = pool.apr > 0 ? `${pool.apr.toFixed(2)}%` : '—';
      const feeStr = `${(parseFloat(pool.fee) * 100).toFixed(2)}%`;

      console.log(`  ${pad(pool.chain, 14)}${S.b}${pad(pool.symbol, 8)}${S.x}${S.y}${pad(balStr, 18)}${S.x}${S.g}${pad(aprStr, 10)}${S.x}${S.d}${feeStr}${S.x}`);
    }

    if (pools.length > 15) {
      console.log(`  ${S.d}... and ${pools.length - 15} more pools${S.x}`);
    }
  } catch (err) {
    console.log(`  ${S.r}Failed to fetch: ${err instanceof Error ? err.message : String(err)}${S.x}`);
  }
}

// ─── Live Routing Quotes ────────────────────────────────────

async function queryLiveQuotes(): Promise<void> {
  section('LIVE ROUTING QUOTES');
  console.log('');
  console.log(`  ${S.d}Fetching real-time quotes from all bridges...${S.x}`);
  console.log('');

  const routes: Array<{ src: Chain; dst: Chain; amount: number }> = [
    { src: 'ethereum', dst: 'solana', amount: 10_000 },
    { src: 'ethereum', dst: 'arbitrum', amount: 50_000 },
    { src: 'solana', dst: 'ethereum', amount: 25_000 },
  ];

  const fullRouter = new MnmxRouter({ strategy: 'minimax', maxHops: 3, logLevel: LogLevel.Silent });
  fullRouter.registerBridge(new WormholeAdapter());
  fullRouter.registerBridge(new DeBridgeAdapter());
  fullRouter.registerBridge(new LayerZeroAdapter());
  fullRouter.registerBridge(new AllbridgeAdapter());

  for (const route of routes) {
    console.log(`  ${S.b}${S.w}${$f(route.amount)} USDC${S.x}  ${NAME[route.src]} → ${NAME[route.dst]}`);
    console.log(`  ${S.d}${ln()}${S.x}`);
    console.log('');

    // Table header
    console.log(`  ${S.d}${pad('Bridge', 16)}${pad('Output', 14)}${pad('Fees', 12)}${pad('Slippage', 10)}${pad('Time', 10)}${pad('Score', 8)}${S.x}`);
    console.log(`  ${S.d}${ln()}${S.x}`);

    const bridges = ['wormhole', 'debridge', 'layerzero', 'allbridge'];
    const results: Array<{ name: string; output: number; fees: number; slip: number; time: number; score: number }> = [];

    for (const bridgeName of bridges) {
      try {
        const singleRouter = new MnmxRouter({ strategy: 'minimax', maxHops: 1, logLevel: LogLevel.Silent });
        if (bridgeName === 'wormhole') singleRouter.registerBridge(new WormholeAdapter());
        else if (bridgeName === 'debridge') singleRouter.registerBridge(new DeBridgeAdapter());
        else if (bridgeName === 'layerzero') singleRouter.registerBridge(new LayerZeroAdapter());
        else if (bridgeName === 'allbridge') singleRouter.registerBridge(new AllbridgeAdapter());

        const result = await singleRouter.findRoute({
          from: { chain: route.src, token: 'USDC', amount: route.amount.toString() },
          to: { chain: route.dst, token: 'USDC' },
        });

        if (result.bestRoute) {
          const r = result.bestRoute;
          const output = parseFloat(r.expectedOutput);
          const fees = parseFloat(r.totalFees);
          const slip = r.path.reduce((s, h) => s + h.slippageBps, 0);

          results.push({ name: bridgeName, output, fees, slip, time: r.estimatedTime, score: r.minimaxScore });
        }
      } catch {
        // Bridge doesn't support this route
      }
    }

    // Sort by score descending
    results.sort((a, b) => b.score - a.score);

    for (const r of results) {
      const isBest = r === results[0];
      const pre = isBest ? `${S.g}${S.b}` : '';
      const suf = isBest ? ` ◀${S.x}` : S.x;
      const tm = r.time >= 60 ? `${Math.floor(r.time / 60)}m ${r.time % 60}s` : `${r.time}s`;

      console.log(`  ${pre}${pad(r.name, 16)}${pad($f(r.output), 14)}${pad($f(r.fees), 12)}${pad(r.slip + ' bps', 10)}${pad(tm, 10)}${r.score.toFixed(4)}${suf}`);
    }

    // MNMX selection
    const mnmxResult = await fullRouter.findRoute({
      from: { chain: route.src, token: 'USDC', amount: route.amount.toString() },
      to: { chain: route.dst, token: 'USDC' },
    });

    if (mnmxResult.bestRoute) {
      const best = mnmxResult.bestRoute;
      const bridge = best.path.map(h => h.bridge).join(' + ');
      const path = best.path.map(h => NAME[h.fromChain]).join(' → ') + ' → ' + NAME[best.path[best.path.length - 1].toChain];

      console.log('');
      console.log(`  ${S.g}${S.b}MNMX Selection:${S.x}  ${S.b}${bridge}${S.x} ${S.d}(${path})${S.x}`);
      console.log(`  ${S.d}Minimax score:${S.x}   ${best.minimaxScore.toFixed(4)}`);
      console.log(`  ${S.d}Guaranteed min:${S.x}  ${parseFloat(best.guaranteedMinimum).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })} USDC ${S.d}(worst-case floor)${S.x}`);
      console.log(`  ${S.d}Evaluated:${S.x}       ${mnmxResult.stats.candidateCount} routes, ${mnmxResult.stats.nodesPruned} pruned in ${mnmxResult.stats.searchTimeMs}ms`);
    }

    console.log('');
  }
}

// ─── Main ───────────────────────────────────────────────────

async function main(): Promise<void> {
  header();
  await sleep(800);

  const start = Date.now();
  console.log(`  ${S.d}Timestamp: ${new Date().toISOString()}${S.x}`);
  console.log(`  ${S.d}Querying live bridge infrastructure...${S.x}`);
  await sleep(600);

  await queryBridgeHealth();
  await sleep(800);
  await queryWormholeNetwork();
  await sleep(800);
  await queryDeBridgeNetwork();
  await sleep(800);
  await queryAllbridgePools();
  await sleep(800);
  await queryLiveQuotes();
  await sleep(700);

  const elapsed = ((Date.now() - start) / 1000).toFixed(1);

  section('STATUS');
  console.log('');
  console.log(`  ${S.d}All data above was queried ${S.b}live${S.x}${S.d} from bridge APIs.${S.x}`);
  console.log(`  ${S.d}Total query time: ${S.b}${elapsed}s${S.x}`);
  console.log('');
  console.log(`  ${S.d}This is the data MNMX uses to make routing decisions.${S.x}`);
  console.log(`  ${S.d}Every quote, every pool balance, every health metric — real-time.${S.x}`);
  console.log('');
  console.log(`  ${S.d}Engine:${S.x}  ${S.c}github.com/MEMX-labs/mnmx${S.x}`);
  console.log(`  ${S.d}Docs:${S.x}    ${S.c}mnmx.app/docs${S.x}`);
  console.log('');
  console.log(`  ${S.d}${ln('═')}${S.x}`);
  console.log('');
}

main().catch((err) => {
  console.error(`\n  ${S.r}Fatal: ${err instanceof Error ? err.message : String(err)}${S.x}\n`);
  process.exit(1);
});
