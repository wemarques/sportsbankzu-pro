/** @type {import('next').NextConfig} */
const nextConfig = {
  // Allow external images (team logos, venue images)
  images: {
    remotePatterns: [
      { protocol: "https", hostname: "**" },
    ],
  },
  // Proxy API routes use server-side env var PY_BACKEND_URL
  // Client-side fetches use NEXT_PUBLIC_PY_BACKEND_URL
};
module.exports = nextConfig;
