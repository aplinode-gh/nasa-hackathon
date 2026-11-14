/**
 * Static UI build: there is no database in this app.
 *
 * Pages that would normally load data get empty results so they render their
 * built-in empty/fallback states ("no farms yet", "not found", etc.) instead
 * of throwing. No DATABASE_URL or network access is required.
 */

const EMPTY: never[] = [];

/** Execute a query — always returns an empty row set in the static build. */
export async function query<T = unknown>(
  _sql: string,
  _values?: unknown[],
): Promise<T[]> {
  return EMPTY as T[];
}

/** Execute a query and return the first row — always null in the static build. */
export async function queryOne<T = unknown>(
  _sql: string,
  _values?: unknown[],
): Promise<T | null> {
  return null;
}

/** Transactions are not available without a database. */
export async function withClient<T>(
  _fn: (client: unknown) => Promise<T>,
): Promise<T> {
  throw new Error("Database access is disabled in the static UI build.");
}

/** Transactions are not available without a database. */
export async function withTransaction<T>(
  _fn: (client: unknown) => Promise<T>,
): Promise<T> {
  throw new Error("Database access is disabled in the static UI build.");
}
