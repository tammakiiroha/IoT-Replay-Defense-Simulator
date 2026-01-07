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
  // Optional: If deploying to a subdirectory (e.g. username.github.io/repo-name), 
  // you might need 'basePath' later, but for now we keep it simple.
};

export default nextConfig;
