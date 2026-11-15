//@ts-check

const withSerwistInit = require("@serwist/next").default;

const withSerwist = withSerwistInit({
  swSrc: "src/lib/serwist/sw.ts",
  swDest: "public/sw.js",
  globPublicPatterns: ["**/*.{js,css,html,ico,png,webp,svg,woff2}"],
  injectionPoint: "self.__WB_MANIFEST",
  disable: process.env.NODE_ENV !== "production",
  register: true,
  reloadOnOnline: true,
});

/** @type {import('next').NextConfig} */
const baseConfig = {
  experimental: {
    globalNotFound: true,
    useOffline: true,
  },
  typescript: {
    ignoreBuildErrors: false,
  },
  async rewrites() {
    const backendUrl = process.env.BACKEND_URL || 'http://localhost:8000';
    return [
      {
        source: '/api/:path*',
        destination: `${backendUrl}/api/:path*`,
      },
    ];
  },
  async headers() {
    return [
      {
        source: "/sw.js",
        headers: [
          { key: "Content-Type", value: "application/javascript" },
          { key: "Cache-Control", value: "no-cache, no-store, must-revalidate" },
        ],
      },
      {
        source: "/manifest.webmanifest",
        headers: [
          { key: "Cache-Control", value: "max-age=0, must-revalidate" },
        ],
      },
    ];
  },
};

module.exports = withSerwist(baseConfig);
