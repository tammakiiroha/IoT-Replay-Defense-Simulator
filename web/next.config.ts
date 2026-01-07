import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: 'export',
  images: {
    unoptimized: true, // Required for static export
  },
  typescript: {
    ignoreBuildErrors: true,
  },
  eslint: {
    ignoreDuringBuilds: true,
  },
  // Deploying to subdirectory: https://username.github.io/repo-name/
  basePath: "/IoT-Replay-Defense-Simulator",
};

export default nextConfig;
