import { useEffect } from "react";

const SITE = "https://www.magi-stream.online";
const DEFAULT_IMAGE = `${SITE}/og-image.png`;

interface SeoProps {
  title: string;
  description: string;
  path?: string;
  image?: string;
  type?: "website" | "video.tv_show" | "video.movie";
  noindex?: boolean;
  jsonLd?: Record<string, unknown> | Record<string, unknown>[];
}

function setMeta(attr: "name" | "property", key: string, content: string) {
  let el = document.head.querySelector<HTMLMetaElement>(`meta[${attr}="${key}"]`);
  if (!el) {
    el = document.createElement("meta");
    el.setAttribute(attr, key);
    document.head.appendChild(el);
  }
  el.setAttribute("content", content);
}

function setLink(rel: string, href: string) {
  let el = document.head.querySelector<HTMLLinkElement>(`link[rel="${rel}"]`);
  if (!el) {
    el = document.createElement("link");
    el.setAttribute("rel", rel);
    document.head.appendChild(el);
  }
  el.setAttribute("href", href);
}

/** SEO par page (sans dépendance) : title, description, canonical, Open Graph, Twitter, JSON-LD. */
export function Seo({ title, description, path = "/", image, type = "website", noindex, jsonLd }: SeoProps) {
  const url = `${SITE}${path}`;
  const img = image || DEFAULT_IMAGE;
  const ld = jsonLd ? JSON.stringify(jsonLd) : "";

  useEffect(() => {
    document.title = title;
    setMeta("name", "description", description);
    setMeta("name", "robots", noindex ? "noindex, nofollow" : "index, follow, max-image-preview:large");
    setLink("canonical", url);

    setMeta("property", "og:title", title);
    setMeta("property", "og:description", description);
    setMeta("property", "og:url", url);
    setMeta("property", "og:type", type);
    setMeta("property", "og:image", img);
    setMeta("property", "og:locale", "fr_FR");
    setMeta("property", "og:site_name", "Magi-Stream");
    setMeta("name", "twitter:card", "summary_large_image");
    setMeta("name", "twitter:title", title);
    setMeta("name", "twitter:description", description);
    setMeta("name", "twitter:image", img);

    const id = "seo-jsonld";
    document.getElementById(id)?.remove();
    if (ld) {
      const s = document.createElement("script");
      s.id = id;
      s.type = "application/ld+json";
      s.text = ld;
      document.head.appendChild(s);
    }
    return () => {
      document.getElementById(id)?.remove();
    };
  }, [title, description, url, img, type, noindex, ld]);

  return null;
}

export default Seo;
