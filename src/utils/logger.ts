/**
 * MNMX Structured Logger
 *
 * Provides leveled, context-tagged logging with formatted timestamps.
 * Each logger instance carries a module tag so that log output can be
 * filtered by subsystem without global configuration changes.
 *
 * Usage:
 *   const log = new Logger('engine:minimax');
 *   log.info('Search started', { depth: 6, actions: 12 });
 *   log.debug('Node evaluated', { hash: 'abc123', score: 0.75 });
 */

// ── Log Levels ───────────────────────────────────────────────────────

export enum LogLevel {
  DEBUG = 0,
  INFO = 1,
  WARN = 2,
  ERROR = 3,
}

const LEVEL_LABELS: Record<LogLevel, string> = {
  [LogLevel.DEBUG]: 'DEBUG',
  [LogLevel.INFO]: 'INFO ',
  [LogLevel.WARN]: 'WARN ',
  [LogLevel.ERROR]: 'ERROR',
};

// ── Log Entry ────────────────────────────────────────────────────────

export interface LogEntry {
  readonly timestamp: string;
  readonly level: LogLevel;
  readonly module: string;
  readonly message: string;
  readonly data?: Record<string, unknown>;
}

// ── Global State ─────────────────────────────────────────────────────

/** Global minimum log level. Messages below this level are discarded. */
let globalMinLevel: LogLevel = LogLevel.INFO;

/** Per-module overrides. If a module is listed here, its level takes precedence. */
const moduleOverrides: Map<string, LogLevel> = new Map();

/** Collected log entries for programmatic access. */
const logBuffer: LogEntry[] = [];

/** Maximum number of entries retained in the buffer. */
let maxBufferSize = 10_000;

/** Whether to write to the console. */
let consoleEnabled = true;

// ── Global Configuration ─────────────────────────────────────────────

/**
 * Set the global minimum log level.
 */
export function setGlobalLogLevel(level: LogLevel): void {
  globalMinLevel = level;
}

/**
 * Override the log level for a specific module.
 */
export function setModuleLogLevel(module: string, level: LogLevel): void {
  moduleOverrides.set(module, level);
}

/**
 * Remove the log level override for a specific module.
 */
export function clearModuleLogLevel(module: string): void {
  moduleOverrides.delete(module);
}

/**
 * Enable or disable console output globally.
 */
export function setConsoleEnabled(enabled: boolean): void {
  consoleEnabled = enabled;
}

/**
 * Set the maximum number of log entries retained in the internal buffer.
 */
export function setMaxBufferSize(size: number): void {
  maxBufferSize = Math.max(0, size);
  while (logBuffer.length > maxBufferSize) {
    logBuffer.shift();
  }
}

/**
 * Retrieve all buffered log entries. Returns a shallow copy.
 */
export function getLogBuffer(): LogEntry[] {
  return [...logBuffer];
}

/**
 * Clear the internal log buffer.
 */
export function clearLogBuffer(): void {
  logBuffer.length = 0;
}

// ── Logger Class ─────────────────────────────────────────────────────

export class Logger {
  private readonly module: string;

  constructor(module: string) {
    this.module = module;
  }
