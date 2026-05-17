import path from "node:path";
import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Minimal Node server bundle for the Coolify Dockerfile.
  output: "standalone",
  // Pin the Turbopack workspace root to this directory so Next doesn't get
  // confused by a stray lockfile higher up the tree.
  turbopack: {
    root: path.join(__dirname),
  },
};

export default nextConfig;
