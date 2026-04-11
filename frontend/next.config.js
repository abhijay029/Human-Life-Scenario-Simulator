/** @type {import('next').NextConfig} */
const nextConfig = {
  // Proxy /api/* to the FastAPI backend
  async rewrites() {
    return [
      {
        source: '/api/:path*',
        destination: 'http://localhost:8000/:path*',
      },
    ]
  },
  // Allow long-running simulation requests (in seconds)
  experimental: {
    proxyTimeout: 480,   // 8 minutes
  },
}

module.exports = nextConfig
