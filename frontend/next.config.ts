import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Emits .next/standalone (a minimal server.js plus traced node_modules) for the Docker image.
  output: "standalone",
  poweredByHeader: false,
};

export default nextConfig;
