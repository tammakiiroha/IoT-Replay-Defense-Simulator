import type { NextConfig } from "next";

const defaultBasePath =
  process.env.NODE_ENV === "production" ? "/IoT-Replay-Defense-Simulator" : "";
const configuredBasePath = process.env.NEXT_PUBLIC_BASE_PATH ?? defaultBasePath;

const nextConfig: NextConfig = {
  output: 'export',
  outputFileTracingRoot: process.cwd(),
  images: {
    unoptimized: true, // Required for static export
  },
  // Use a repo sub-path in production, but keep local dev at root by default.
  ...(configuredBasePath ? { basePath: configuredBasePath } : {}),
};

export default nextConfig;
