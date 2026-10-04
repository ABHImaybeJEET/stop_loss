import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
    "./context/**/*.{js,ts,jsx,tsx,mdx}",
    "./lib/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        background: "#ffffff",
        foreground: "#09090b",
        // Terminal design tokens: monochrome editorial + one gain/loss pair.
        ink: { DEFAULT: "#111111", soft: "#333333" },
        muted: { DEFAULT: "#6B6A66", soft: "#A1A09A" },
        line: { DEFAULT: "#EAEAEA", strong: "#D4D4D4" },
        canvas: "#FAFAFA",
        subtle: "#F4F4F2",
        gain: { DEFAULT: "#047857", soft: "#ECFDF5" },
        loss: { DEFAULT: "#BE123C", soft: "#FFF1F2" },
      },
      fontFamily: {
        sans: ["Avenir Next", "Avenir", "Segoe UI Variable", "Segoe UI", "sans-serif"],
        editorial: ["Iowan Old Style", "Palatino Linotype", "Book Antiqua", "Georgia", "serif"],
        mono: ["Geist Mono", "JetBrains Mono", "monospace"],
      },
      fontSize: {
        "2xs": ["10px", { lineHeight: "14px" }],
      },
      maxWidth: {
        terminal: "52rem",
      },
    },
  },
  plugins: [],
};
export default config;
