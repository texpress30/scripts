export interface Country {
  id: string;
  name: string;
}

export interface Channel {
  id: string;
  name: string;
  category: "popular" | "other";
}

export const COUNTRIES: Country[] = [
  { id: "0", name: "United States" },
  { id: "21", name: "Argentina" },
  { id: "2", name: "Australia" },
  { id: "12", name: "Austria" },
  { id: "10", name: "Belgium" },
  { id: "69", name: "Bosnia and Herzegovina" },
  { id: "8", name: "Brazil" },
  { id: "63", name: "Bulgaria" },
  { id: "9", name: "Canada" },
  { id: "42", name: "Chile" },
  { id: "39", name: "China" },
  { id: "40", name: "Colombia" },
  { id: "65", name: "Costa Rica" },
  { id: "68", name: "Croatia" },
  { id: "53", name: "Cyprus" },
  { id: "28", name: "Czech Republic" },
  { id: "17", name: "Denmark" },
  { id: "58", name: "Estonia" },
  { id: "14", name: "Finland" },
  { id: "5", name: "France" },
  { id: "3", name: "Germany" },
  { id: "24", name: "Greece" },
  { id: "44", name: "Hong Kong" },
  { id: "27", name: "Hungary" },
  { id: "11", name: "India" },
  { id: "34", name: "Indonesia" },
  { id: "29", name: "Ireland" },
  { id: "49", name: "Israel" },
  { id: "6", name: "Italy" },
  { id: "30", name: "Japan" },
  { id: "37", name: "Latvia" },
  { id: "57", name: "Lithuania" },
  { id: "56", name: "Luxembourg" },
  { id: "31", name: "Malaysia" },
  { id: "55", name: "Malta" },
  { id: "18", name: "Mexico" },
  { id: "59", name: "Monaco" },
  { id: "1", name: "Netherlands" },
  { id: "22", name: "New Zealand" },
  { id: "66", name: "Nicaragua" },
  { id: "62", name: "Nigeria" },
  { id: "15", name: "Norway" },
  { id: "64", name: "Pakistan" },
  { id: "67", name: "Panama" },
  { id: "41", name: "Peru" },
  { id: "36", name: "Philippines" },
  { id: "16", name: "Poland" },
  { id: "25", name: "Portugal" },
  { id: "52", name: "Qatar" },
  { id: "38", name: "Romania" },
  { id: "13", name: "Russia" },
  { id: "60", name: "San Marino" },
  { id: "50", name: "Saudi Arabia" },
  { id: "32", name: "Singapore" },
  { id: "26", name: "Slovakia" },
  { id: "54", name: "Slovenia" },
  { id: "33", name: "South Africa" },
  { id: "43", name: "South Korea" },
  { id: "4", name: "Spain" },
  { id: "19", name: "Sweden" },
  { id: "23", name: "Switzerland" },
  { id: "45", name: "Taiwan" },
  { id: "35", name: "Thailand" },
  { id: "20", name: "Turkey" },
  { id: "46", name: "UAE" },
  { id: "51", name: "Ukraine" },
  { id: "7", name: "United Kingdom" },
  { id: "61", name: "Vatican City" },
  { id: "48", name: "Vietnam" },
];

export const COMMON_CHANNELS: Channel[] = [
  { id: "google_shopping", name: "Google Shopping", category: "popular" },
  { id: "bing", name: "Bing", category: "popular" },
  { id: "facebook_product_ads", name: "Facebook Product Ads", category: "popular" },
  { id: "google_local_inventory", name: "Google Local Product Inventory Feed", category: "popular" },
  { id: "custom", name: "Custom channel", category: "other" },
  { id: "daisycon", name: "Daisycon", category: "other" },
  { id: "facebook_country", name: "Facebook Country Feed", category: "other" },
  { id: "facebook_language", name: "Facebook Language Feed", category: "other" },
  { id: "google_product_reviews", name: "Google Product Reviews", category: "other" },
  { id: "klarna", name: "Klarna", category: "other" },
  { id: "regional_inventory", name: "Regional Product Inventory Feed", category: "other" },
];

export const COUNTRY_SPECIFIC_CHANNELS: Record<string, Channel[]> = {
  "38": [
    { id: "compari_ro", name: "Compari", category: "other" },
    { id: "glami_ro", name: "Glami.ro", category: "other" },
    { id: "okazii_ro", name: "Okazii.ro", category: "other" },
    { id: "price_ro", name: "Price.ro", category: "other" },
    { id: "shopmania_ro", name: "Shopmania.ro", category: "other" },
    { id: "shopmania_ro_csv", name: "Shopmania.ro (CSV)", category: "other" },
  ],
};

const ISO_MAP: Record<string, string> = {
  "0": "US", "21": "AR", "2": "AU", "12": "AT", "10": "BE",
  "69": "BA", "8": "BR", "63": "BG", "9": "CA", "42": "CL",
  "39": "CN", "40": "CO", "65": "CR", "68": "HR", "53": "CY",
  "28": "CZ", "17": "DK", "58": "EE", "14": "FI", "5": "FR",
  "3": "DE", "24": "GR", "44": "HK", "27": "HU", "11": "IN",
  "34": "ID", "29": "IE", "49": "IL", "6": "IT", "30": "JP",
  "37": "LV", "57": "LT", "56": "LU", "31": "MY", "55": "MT",
  "18": "MX", "59": "MC", "1": "NL", "22": "NZ", "66": "NI",
  "62": "NG", "15": "NO", "64": "PK", "67": "PA", "41": "PE",
  "36": "PH", "16": "PL", "25": "PT", "52": "QA", "38": "RO",
  "13": "RU", "60": "SM", "50": "SA", "32": "SG", "26": "SK",
  "54": "SI", "33": "ZA", "43": "KR", "4": "ES", "19": "SE",
  "23": "CH", "45": "TW", "35": "TH", "20": "TR", "46": "AE",
  "51": "UA", "7": "GB", "61": "VA", "48": "VN",
};

export function getCountryISOCode(countryId: string): string {
  return ISO_MAP[countryId] || countryId;
}

export function getChannelsForCountry(countryId: string): { popular: Channel[]; other: Channel[] } {
  const popular = COMMON_CHANNELS.filter((c) => c.category === "popular");
  const commonOther = COMMON_CHANNELS.filter((c) => c.category === "other");
  const countrySpecific = COUNTRY_SPECIFIC_CHANNELS[countryId] || [];

  return {
    popular,
    other: [...commonOther, ...countrySpecific].sort((a, b) => a.name.localeCompare(b.name)),
  };
}
