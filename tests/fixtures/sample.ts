/** Generic fixture for capsule extraction tests. */
export interface SearchTarget {
  readonly path: string;
  readonly line: number;
}

export type SearchMode = "exact" | "semantic";

export enum SearchStatus {
  Idle = "idle",
  Running = "running",
  Done = "done",
}

export class CatalogSearcher {
  search(query: string): SearchTarget[] {
    return [];
  }

  rank(targets: SearchTarget[]): SearchTarget[] {
    return targets;
  }
}

export function buildCapsule(query: string, limit = 12): string {
  return `${query}:${limit}`;
}

export const DEFAULT_LIMIT = 12;
