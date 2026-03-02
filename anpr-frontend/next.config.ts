import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Allow blob: URLs in <img> tags (used for local file previews)
  images: {
    unoptimized: true,
  },
  // Proxy API requests to the FastAPI backend during development
  async rewrites() {
    return [
      {
        source: "/api/:path*",
        destination: "http://localhost:8000/:path*",
      },
    ];
  },
};

export default nextConfig;
