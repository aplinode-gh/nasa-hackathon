/**
 * Service worker entry point compiled by @serwist/next (InjectManifest).
 * Uses a minimal custom SW shell to precache build assets and provide
 * navigation fallback to /offline while avoiding Serwist runtime init issues.
 */

/// <reference lib="webworker" />
declare const self: ServiceWorkerGlobalScope & {
  __WB_MANIFEST: Array<string | { url: string; revision: string | null }>;
};

const PRECACHE_MANIFEST: Array<string | { url: string; revision: string | null }> =
  (self.__WB_MANIFEST as unknown as Array<string | { url: string; revision: string | null }>) ?? [];

const PRECACHE_CACHE = "agroai-precache-v1";
const NAV_FALLBACK = "/offline";

self.addEventListener("install", (event) => {
  event.waitUntil(
    (async () => {
      const cache = await caches.open(PRECACHE_CACHE);
      await Promise.all(
        PRECACHE_MANIFEST.map(async (entry) => {
          const url = typeof entry === "string" ? entry : entry.url;
          try {
            await cache.add(url);
          } catch {
            // Ignore individual precache failures so one bad asset doesn't
            // abort the whole install.
          }
        }),
      );
      await self.skipWaiting();
    })(),
  );
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    (async () => {
      const keys = await caches.keys();
      await Promise.all(
        keys
          .filter((k) => k.startsWith("agroai-precache-") && k !== PRECACHE_CACHE)
          .map((k) => caches.delete(k)),
      );
      await self.clients.claim();
    })(),
  );
});

self.addEventListener("fetch", (event) => {
  const req = event.request;
  if (req.method !== "GET") return;
  const url = new URL(req.url);
  if (url.origin !== self.location.origin) return;

  event.respondWith(
    (async () => {
      const cache = await caches.open(PRECACHE_CACHE);
      const cached = await cache.match(req);
      if (cached) return cached;
      try {
        const fresh = await fetch(req);
        return fresh;
      } catch {
        if (req.mode === "navigate") {
          const fallback = await cache.match(NAV_FALLBACK);
          if (fallback) return fallback;
        }
        return new Response("", { status: 504, statusText: "Offline" });
      }
    })(),
  );
});
