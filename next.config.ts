import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Keep the dev-only badge away from the sidebar's sign-out button.
  devIndicators: { position: "bottom-right" },
};

export default nextConfig;
