/**
 * Formats a canonical source video timestamp (in seconds) into a readable MM:SS.S string.
 * This is used to present exact video event times across the application.
 *
 * @param seconds - The raw timestamp from the backend (e.g. 2.702)
 * @returns Formatted string (e.g. "00:02.7") or "Source time unavailable"
 */
export function formatVideoTimestamp(seconds: number | string | null | undefined): string {
  if (seconds === null || seconds === undefined) return 'Source time unavailable';
  
  const parsed = typeof seconds === 'string' ? parseFloat(seconds) : seconds;
  if (Number.isNaN(parsed) || !isFinite(parsed) || parsed < 0) {
    return 'Source time unavailable';
  }

  const m = Math.floor(parsed / 60);
  const s = Math.floor(parsed % 60);
  const ms = Math.floor((parsed % 1) * 10); // get tenths of a second

  const padM = m.toString().padStart(2, '0');
  const padS = s.toString().padStart(2, '0');

  return `${padM}:${padS}.${ms}`;
}
