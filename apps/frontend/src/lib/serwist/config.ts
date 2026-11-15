/**
 * Serwist service worker runtime caching config.
 * Based on the PWA setup used in the boilerplate app.
 */

import {
  NetworkFirst,
  CacheFirst,
  StaleWhileRevalidate,
  ExpirationPlugin,
} from "serwist";
import type { RuntimeCaching } from "serwist";

const twentyFourHours = 24 * 60 * 60;

export const runtimeCaching: RuntimeCaching[] = [
  {
    matcher: ({ url }) => url.pathname.startsWith("/api/"),
    handler: new NetworkFirst({
      cacheName: "api-cache",
      networkTimeoutSeconds: 10,
      plugins: [
        new ExpirationPlugin({
          maxAgeSeconds: twentyFourHours,
          maxEntries: 100,
        }),
      ],
    }),
  },
  {
    matcher: ({ request }) => request.destination === "image",
    handler: new CacheFirst({
      cacheName: "images",
      plugins: [
        new ExpirationPlugin({
          maxAgeSeconds: 30 * twentyFourHours,
          maxEntries: 200,
        }),
      ],
    }),
  },
  {
    matcher: ({ request }) => request.destination === "font",
    handler: new CacheFirst({
      cacheName: "fonts",
      plugins: [
        new ExpirationPlugin({
          maxAgeSeconds: 365 * twentyFourHours,
          maxEntries: 50,
        }),
      ],
    }),
  },
  {
    matcher: ({ request }) =>
      request.destination === "script" || request.destination === "style",
    handler: new StaleWhileRevalidate({
      cacheName: "static-assets",
      plugins: [
        new ExpirationPlugin({
          maxAgeSeconds: 7 * twentyFourHours,
          maxEntries: 100,
        }),
      ],
    }),
  },
  {
    matcher: ({ url }) =>
      url.pathname.startsWith("/_next/data/") ||
      url.pathname.startsWith("/_next/static/"),
    handler: new StaleWhileRevalidate({
      cacheName: "next-data",
      plugins: [
        new ExpirationPlugin({
          maxAgeSeconds: 7 * twentyFourHours,
          maxEntries: 200,
        }),
      ],
    }),
  },
];

export default runtimeCaching;
