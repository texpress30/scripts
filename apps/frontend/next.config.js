const withBundleAnalyzer = require("@next/bundle-analyzer")({
  enabled: process.env.ANALYZE === "true",
});

// Resolve the FastAPI backend URL at build time. Mirrors the fallback chain
// used by ``apps/frontend/src/app/api/[...path]/route.ts`` so local dev,
// Vercel previews, and Railway production all pick the same target.
function getBackendBaseUrl() {
  const configured =
    process.env.BACKEND_API_URL ??
    process.env.NEXT_PUBLIC_API_BASE_URL ??
    "http://localhost:8000";
  return configured.replace(/\/+$/, "");
}

/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  experimental: {
    optimizePackageImports: ["lucide-react"],
  },
  // BigCommerce OAuth callbacks proxy.
  //
  // When a merchant installs the Voxel app from the BigCommerce App
  // Marketplace, BigCommerce redirects the merchant browser directly to the
  // four callback URLs registered in the Developer Portal:
  //
  //   * /agency/integrations/bigcommerce/callback    (auth/install)
  //   * /agency/integrations/bigcommerce/load        (app launch inside BC)
  //   * /agency/integrations/bigcommerce/uninstall   (merchant removes app)
  //   * /agency/integrations/bigcommerce/remove_user (multi-user revoke)
  //
  // Those URLs hit this Next.js frontend on ``admin.omarosa.ro`` — but the
  // actual handlers live on the FastAPI backend under a slightly different
  // path (``/integrations/bigcommerce/auth/<name>`` without the ``/agency``
  // prefix, and with ``remove-user`` instead of ``remove_user``). Without
  // these rewrites the merchant hits a Next.js 404 instead of the OAuth
  // handler.
  //
  // The rewrites only cover the four unauthenticated callback paths — the
  // CRUD + test-connection endpoints are hit by the in-app wizard via the
  // generic ``/api/[...path]`` proxy (which requires an auth token), so they
  // do not need a dedicated rewrite here.
  async rewrites() {
    const backend = getBackendBaseUrl();
    return [
      {
        source: "/agency/integrations/bigcommerce/callback",
        destination: `${backend}/integrations/bigcommerce/auth/callback`,
      },
      {
        source: "/agency/integrations/bigcommerce/load",
        destination: `${backend}/integrations/bigcommerce/auth/load`,
      },
      {
        source: "/agency/integrations/bigcommerce/uninstall",
        destination: `${backend}/integrations/bigcommerce/auth/uninstall`,
      },
      {
        source: "/agency/integrations/bigcommerce/remove_user",
        destination: `${backend}/integrations/bigcommerce/auth/remove-user`,
      },
    ];
  },
};

module.exports = withBundleAnalyzer(nextConfig);
