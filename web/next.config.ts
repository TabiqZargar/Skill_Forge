import type { NextConfig } from "next";

// The FastAPI backend. In local dev this points at the uvicorn server; on
// DigitalOcean App Platform it points at the internal service URL.
const apiOrigin = (process.env.API_ORIGIN || "http://localhost:8000").replace(/\/+$/, "");

const nextConfig: NextConfig = {
  cacheComponents: true,
  partialPrefetching: true,
  turbopack: {
    rules: {
      "*.css": {
        loaders: ["@tailwindcss/turbopack"],
        as: "*.css",
      },
    },
  },
  async rewrites() {
    return [
      {
        source: "/api/:path*",
        destination: `${apiOrigin}/api/:path*`,
      },
    ];
  },
};

export default nextConfig;
