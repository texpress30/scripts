/**
 * Channel definitions grouped by platform.
 * Replaces the old country-based channel-config for the new modal.
 * Slugs are stable identifiers; display names are user-facing.
 */

export interface PlatformChannel {
  slug: string;
  displayName: string;
  compatibleSubtypes: string[];
  hasSchema?: boolean; // will be populated at runtime
}

export interface Platform {
  platform: string;
  displayName: string;
  sortOrder: number;
  channels: PlatformChannel[];
}

export const CHANNEL_PLATFORMS: Platform[] = [
  {
    platform: "google",
    displayName: "Google",
    sortOrder: 1,
    channels: [
      { slug: "google_shopping", displayName: "Google Shopping", compatibleSubtypes: ["product_physical", "product_local", "product_other", "vehicle_listings"] },
      { slug: "google_vehicle_ads_v3", displayName: "Google Vehicle Ads", compatibleSubtypes: ["vehicle_listings"] },
      { slug: "google_vehicle_listings", displayName: "Google Vehicle Listings", compatibleSubtypes: ["vehicle_listings"] },
      { slug: "google_local_inventory", displayName: "Google Local Inventory", compatibleSubtypes: ["product_physical", "product_local"] },
      { slug: "google_product_reviews", displayName: "Google Product Reviews", compatibleSubtypes: ["product_physical", "product_local", "product_other"] },
      { slug: "google_regional_inventory", displayName: "Google Regional Inventory", compatibleSubtypes: ["product_physical", "product_local"] },
      { slug: "google_manufacturers", displayName: "Google Manufacturers Feed", compatibleSubtypes: ["product_physical", "product_other"] },
      { slug: "google_hotel_ads", displayName: "Google Hotel Ads", compatibleSubtypes: ["hotel_standard"] },
      { slug: "google_real_estate", displayName: "Google Real Estate Ads", compatibleSubtypes: ["home_listing_standard"] },
      { slug: "google_jobs", displayName: "Google Jobs", compatibleSubtypes: [] },
      { slug: "google_things_to_do", displayName: "Google Things to Do", compatibleSubtypes: [] },
    ],
  },
  {
    platform: "meta",
    displayName: "Meta",
    sortOrder: 2,
    channels: [
      { slug: "facebook_product_ads", displayName: "Meta Automotive Catalog", compatibleSubtypes: ["vehicle_offers", "vehicle_listings"] },
      { slug: "facebook_country", displayName: "Meta Country Feed", compatibleSubtypes: ["product_physical", "product_local", "product_other"] },
      { slug: "facebook_language", displayName: "Meta Language Feed", compatibleSubtypes: ["product_physical", "product_local", "product_other"] },
      { slug: "facebook_marketplace", displayName: "Facebook Marketplace", compatibleSubtypes: ["product_physical", "product_local", "product_other"] },
      { slug: "facebook_automotive", displayName: "Meta Automotive Ads", compatibleSubtypes: ["vehicle_offers", "vehicle_listings"] },
      { slug: "facebook_hotel", displayName: "Meta Hotel Ads", compatibleSubtypes: ["hotel_standard"] },
      { slug: "facebook_streaming_ads", displayName: "Facebook Streaming Ads", compatibleSubtypes: ["media_multishow", "media_card"] },
      { slug: "facebook_destination_ads", displayName: "Facebook Destination Ads", compatibleSubtypes: ["destination_standard"] },
      { slug: "facebook_professional_services", displayName: "Facebook Professional Services", compatibleSubtypes: ["professional_services"] },
    ],
  },
  {
    platform: "tiktok",
    displayName: "TikTok",
    sortOrder: 3,
    channels: [
      { slug: "tiktok_automotive_inventory", displayName: "TikTok Auto-Inventory", compatibleSubtypes: ["vehicle_listings"] },
      { slug: "tiktok", displayName: "TikTok Catalog", compatibleSubtypes: ["product_physical", "product_local", "product_other"] },
      { slug: "tiktok_destination", displayName: "TikTok Destination", compatibleSubtypes: ["destination_standard"] },
    ],
  },
  {
    platform: "bing",
    displayName: "Bing / Microsoft",
    sortOrder: 4,
    channels: [
      { slug: "bing", displayName: "Bing Shopping", compatibleSubtypes: ["product_physical", "product_local", "product_other", "vehicle_listings"] },
    ],
  },
  {
    platform: "social",
    displayName: "Social & Ads",
    sortOrder: 5,
    channels: [
      { slug: "pinterest", displayName: "Pinterest", compatibleSubtypes: ["product_physical", "product_local", "product_other"] },
      { slug: "snapchat", displayName: "Snapchat", compatibleSubtypes: ["product_physical", "product_local", "product_other"] },
      { slug: "linkedin", displayName: "LinkedIn", compatibleSubtypes: ["product_physical", "product_local", "product_other"] },
      { slug: "twitter", displayName: "X (Twitter)", compatibleSubtypes: ["product_physical", "product_local", "product_other"] },
      { slug: "reddit_catalog", displayName: "Reddit Catalog Ads", compatibleSubtypes: ["product_physical", "product_local", "product_other"] },
      { slug: "criteo", displayName: "Criteo", compatibleSubtypes: ["product_physical", "product_local", "product_other"] },
      { slug: "trade_desk", displayName: "The Trade Desk", compatibleSubtypes: ["product_physical", "product_local", "product_other"] },
      { slug: "perplexity", displayName: "Perplexity Shopping", compatibleSubtypes: ["product_physical", "product_local", "product_other"] },
      { slug: "gpt_shopping", displayName: "GPT Shopping", compatibleSubtypes: ["product_physical", "product_local", "product_other"] },
    ],
  },
  {
    platform: "marketplaces_ro",
    displayName: "Marketplace-uri RO",
    sortOrder: 10,
    channels: [
      { slug: "compari_ro", displayName: "Compari.ro", compatibleSubtypes: ["product_physical", "product_local", "product_other"] },
      { slug: "okazii_ro", displayName: "Okazii.ro", compatibleSubtypes: ["product_physical", "product_local", "product_other"] },
      { slug: "price_ro", displayName: "Price.ro", compatibleSubtypes: ["product_physical", "product_local", "product_other"] },
      { slug: "shopmania_ro", displayName: "Shopmania.ro", compatibleSubtypes: ["product_physical", "product_local", "product_other"] },
      { slug: "glami_ro", displayName: "Glami.ro", compatibleSubtypes: ["product_physical", "product_local", "product_other"] },
    ],
  },
  {
    platform: "affiliate",
    displayName: "Affiliate & Payment",
    sortOrder: 15,
    channels: [
      { slug: "daisycon", displayName: "Daisycon", compatibleSubtypes: ["product_physical", "product_local", "product_other"] },
      { slug: "klarna", displayName: "Klarna", compatibleSubtypes: ["product_physical", "product_local", "product_other"] },
      { slug: "awin", displayName: "Awin", compatibleSubtypes: ["product_physical", "product_local", "product_other"] },
      { slug: "shareasale", displayName: "ShareASale", compatibleSubtypes: ["product_physical", "product_local", "product_other"] },
    ],
  },
];

/**
 * Flat lookup: slug → display name (for showing labels from stored channel_type values).
 */
export const CHANNEL_DISPLAY_NAMES: Record<string, string> = {};
export const CHANNEL_PLATFORM_MAP: Record<string, { platform: string; platformDisplayName: string }> = {};

for (const p of CHANNEL_PLATFORMS) {
  for (const ch of p.channels) {
    CHANNEL_DISPLAY_NAMES[ch.slug] = ch.displayName;
    CHANNEL_PLATFORM_MAP[ch.slug] = {
      platform: p.platform,
      platformDisplayName: p.displayName,
    };
  }
}

// Also include legacy labels so old channel_type values resolve
CHANNEL_DISPLAY_NAMES["google_shopping"] ??= "Google Shopping";
CHANNEL_DISPLAY_NAMES["meta_catalog"] ??= "Meta Catalog";
CHANNEL_DISPLAY_NAMES["tiktok_catalog"] ??= "TikTok Catalog";
CHANNEL_DISPLAY_NAMES["custom"] = "Custom";

const PLATFORM_BADGE_COLORS: Record<string, string> = {
  google: "bg-blue-100 text-blue-700 dark:bg-blue-900/40 dark:text-blue-400",
  meta: "bg-indigo-100 text-indigo-700 dark:bg-indigo-900/40 dark:text-indigo-400",
  tiktok: "bg-slate-900 text-white dark:bg-slate-200 dark:text-slate-900",
  bing: "bg-sky-100 text-sky-700 dark:bg-sky-900/40 dark:text-sky-400",
  social: "bg-purple-100 text-purple-700 dark:bg-purple-900/40 dark:text-purple-400",
  marketplaces_ro: "bg-emerald-100 text-emerald-700 dark:bg-emerald-900/40 dark:text-emerald-400",
  affiliate: "bg-amber-100 text-amber-700 dark:bg-amber-900/40 dark:text-amber-400",
};

export function getPlatformBadgeColor(platform: string): string {
  return PLATFORM_BADGE_COLORS[platform] ?? "bg-slate-100 text-slate-600 dark:bg-slate-700 dark:text-slate-400";
}
