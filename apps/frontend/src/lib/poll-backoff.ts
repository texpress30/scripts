/**
 * Exponential backoff helper for polling loops.
 *
 * Formula: min(baseMs * 2^consecutiveIdles, maxMs)
 * Resets to baseMs when activity is detected (data changed).
 */

export function computeBackoffMs(
  baseMs: number,
  consecutiveIdles: number,
  maxMs: number,
): number {
  return Math.min(baseMs * 2 ** consecutiveIdles, maxMs);
}

export class PollBackoff {
  private _idles = 0;
  constructor(
    private readonly baseMs: number,
    private readonly maxMs: number,
    private readonly hiddenMs?: number,
  ) {}

  /** Call when the latest poll returned unchanged data. */
  idle(): void {
    this._idles += 1;
  }

  /** Call when the latest poll returned new/changed data. */
  active(): void {
    this._idles = 0;
  }

  reset(): void {
    this._idles = 0;
  }

  get consecutiveIdles(): number {
    return this._idles;
  }

  /** Next delay in ms, respecting document.hidden. */
  nextMs(): number {
    if (typeof document !== "undefined" && document.hidden) {
      return this.hiddenMs ?? this.maxMs;
    }
    return computeBackoffMs(this.baseMs, this._idles, this.maxMs);
  }
}
