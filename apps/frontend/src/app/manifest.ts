import type { MetadataRoute } from "next";

export default function manifest(): MetadataRoute.Manifest {
  return {
    name: "Agropioo — Farm Intelligence",
    short_name: "Agropioo",
    description:
      "AI-powered farm intelligence for Pakistani farmers: weather, records, disease detection, and market prices — offline capable.",
    start_url: "/?source=pwa",
    display: "standalone",
    background_color: "#F0FDF4",
    theme_color: "#F0FDF4",
    orientation: "portrait",
    icons: [
      {
        src: "/logo.png",
        sizes: "192x192",
        type: "image/png",
      },
      {
        src: "/logo.png",
        sizes: "512x512",
        type: "image/png",
      },
    ],
  };
}
