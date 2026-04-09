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
  // Reverse-proxy rules for backend endpoints that aren't handled by the
  // generic ``/api/[...path]`` proxy route.
  //
  // ``beforeFiles`` — in-app API endpoints. These rules fire BEFORE the
  // ``app/api/[...path]/route.ts`` catch-all, so the request is proxied
  // straight from the Next.js / Vercel edge to the FastAPI backend
  // without going through the catch-all serverless function. Required
  // for the Shopify deferred-claim endpoints shipped in PR #952, which
  // were not picked up correctly by the catch-all on Vercel and returned
  // a 404 "Not Found" from the wizard. The BigCommerce equivalents
  // (``/integrations/bigcommerce/stores/available``, ``/sources/claim``,
  // ``/test-connection``) were added by the PR #942–#948 sequence and
  // the BigCommerce wizard still routes them through the catch-all —
  // this file only adds Shopify rules so we don't accidentally churn
  // BigCommerce traffic.
  //
  // ``afterFiles`` — unauthenticated OAuth merchant callbacks. BigCommerce
  // redirects the merchant browser directly to these four callback URLs
  // registered in the BC Developer Portal:
  //
  //   * /agency/integrations/bigcommerce/callback    (auth/install)
  //   * /agency/integrations/bigcommerce/load        (app launch inside BC)
  //   * /agency/integrations/bigcommerce/uninstall   (merchant removes app)
  //   * /agency/integrations/bigcommerce/remove_user (multi-user revoke)
  //
  // The backend routes don't carry the ``/agency`` prefix and live under
  // ``/integrations/bigcommerce/auth/<name>``; the ``remove_user`` BC
  // marketplace convention maps to our ``remove-user`` FastAPI route
  // (underscore → hyphen). Without these rewrites the merchant hits a
  // Next.js 404 instead of the OAuth handler.
  async rewrites() {
    const backend = getBackendBaseUrl();
    return {
      beforeFiles: [
        // Shopify in-app deferred-claim endpoints. Placed in
        // ``beforeFiles`` so they intercept the ``/api/[...path]``
        // catch-all — the catch-all was returning 404 for these paths
        // on Vercel even though the backend routes exist and local
        // ``next dev`` resolves them correctly.
        {
          source: "/api/integrations/shopify/stores/available",
          destination: `${backend}/integrations/shopify/stores/available`,
        },
        {
          source: "/api/integrations/shopify/sources/claim",
          destination: `${backend}/integrations/shopify/sources/claim`,
        },
        {
          source: "/api/integrations/shopify/test-connection/by-shop",
          destination: `${backend}/integrations/shopify/test-connection/by-shop`,
        },
      ],
      afterFiles: [
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
      ],
      fallback: [],
    };
  },
};

module.exports = withBundleAnalyzer(nextConfig);
