import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: "standalone",
  experimental: {
    staleTimes: {
      dynamic: 0,
      static: 15,
    },
  }
};

export default nextConfig;
