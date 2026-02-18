import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./src/**/*.{js,ts,jsx,tsx,mdx}"],
  theme: {
    extend: {
      colors: {
        brand: {
          500: "#2563eb",
          600: "#1d4ed8"
        }
      }
    }
  },
  plugins: []
};

export default config;
