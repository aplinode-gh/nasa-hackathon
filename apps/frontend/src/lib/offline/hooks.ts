/**
 * Static UI build: offline detection hooks are stubbed.
 *
 * The app always reports itself as online; the offline queue/drain machinery
 * from the original PWA build is not included.
 */
"use client";

export type OfflineStatus = {
  online: boolean;
  canConnect: boolean;
};

const ONLINE: OfflineStatus = { online: true, canConnect: true };

export function useOffline(): boolean {
  return false;
}

export function useOfflineStatus(): OfflineStatus {
  return ONLINE;
}

export function useDrainOnReconnect(): OfflineStatus {
  return ONLINE;
}
