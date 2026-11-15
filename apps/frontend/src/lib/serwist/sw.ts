/**
 * Service worker entry point compiled by @serwist/next (InjectManifest).
 * Uses a minimal custom SW shell to precache build assets and provide
 * navigation fallback to /offline while avoiding Serwist runtime init issues.
 */

export {};

type PrecacheEntry = string | { url: string; revision: string | null };

type SwSelf = {
  __WB_MANIFEST?: PrecacheEntry[];
  location: { origin: string };
  skipWaiting: () => Promise<void> | void;
  clients: { claim: () => Promise<void> | void };
  addEventListener: (type: string, listener: (event: any) => void) => void;
};

const sw = self as unknown as SwSelf;

const PRECACHE_MANIFEST: PrecacheEntry[] = sw.__WB_MANIFEST ?? [];

const PRECACHE_CACHE = "agroai-precache-v1";
const NAV_FALLBACK = "/offline";

sw.addEventListener("install", (event: any) => {
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
      await sw.skipWaiting();
    })(),
  );
});

sw.addEventListener("activate", (event: any) => {
  event.waitUntil(
    (async () => {
      const keys = await caches.keys();
      await Promise.all(
        keys
          .filter((k) => k.startsWith("agroai-precache-") && k !== PRECACHE_CACHE)
          .map((k) => caches.delete(k)),
      );
      await sw.clients.claim();
    })(),
  );
});

sw.addEventListener("fetch", (event: any) => {
  const req: Request = event.request;
  if (!req || req.method !== "GET") return;
  const url = new URL(req.url);
  if (url.origin !== sw.location.origin) return;

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
