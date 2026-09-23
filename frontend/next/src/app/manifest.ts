import type { MetadataRoute } from "next";
export default function manifest(): MetadataRoute.Manifest {
  return {
    name: "sportsbankzu", short_name: "sportsbankzu", start_url: "/jogos", display: "standalone",
    background_color: "#15161A", theme_color: "#15161A",
    icons: [{ src: "/marca/icon-192.png", sizes: "192x192", type: "image/png" }, { src: "/marca/icon-512.png", sizes: "512x512", type: "image/png" }],
  };
}
