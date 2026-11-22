import type { NextConfig } from "next";

// The browser calls /api/* on the web origin; Next proxies to the API. Same origin means the
// session cookie works without CORS. API_URL is read at build time (Docker passes it as a build arg).
const api = process.env.API_URL ?? "http://localhost:8000";

const nextConfig: NextConfig = {
  output: "standalone",
  async rewrites() {
    return [{ source: "/api/:path*", destination: `${api}/api/:path*` }];
  },
};

export default nextConfig;
