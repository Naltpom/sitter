import { useEffect } from "react";
import { useTranslation } from "react-i18next";
import { useAppSettings } from "../AppSettingsContext";

interface PageSEOProps {
  page:
    | "login"
    | "register"
    | "forgot_password"
    | "reset_password"
    | "verify_email"
    | "force_change_password"
    | "accept_invitation";
}

function setMeta(attr: "name" | "property", key: string, content: string) {
  let el = document.querySelector(
    `meta[${attr}="${key}"]`,
  ) as HTMLMetaElement | null;
  if (!el) {
    el = document.createElement("meta");
    el.setAttribute(attr, key);
    document.head.appendChild(el);
  }
  el.content = content;
}

function setCanonical(href: string) {
  let el = document.querySelector(
    'link[rel="canonical"]',
  ) as HTMLLinkElement | null;
  if (!el) {
    el = document.createElement("link");
    el.rel = "canonical";
    document.head.appendChild(el);
  }
  el.href = href;
}

function setJsonLd(data: Record<string, unknown>) {
  let el = document.querySelector(
    'script[data-seo="jsonld"]',
  ) as HTMLScriptElement | null;
  if (!el) {
    el = document.createElement("script");
    el.type = "application/ld+json";
    el.setAttribute("data-seo", "jsonld");
    document.head.appendChild(el);
  }
  el.textContent = JSON.stringify(data);
}

export default function PageSEO({ page }: PageSEOProps) {
  const { settings } = useAppSettings();
  const { t, i18n } = useTranslation("_identity");

  useEffect(() => {
    const appName = settings.app_name || "Sitter";
    const appDesc = settings.app_description || "";
    const origin = window.location.origin;
    const pathname = window.location.pathname;
    const url = origin + pathname;

    const title = t(`seo.${page}_title`, { app_name: appName });
    const description = t(`seo.${page}_description`, {
      app_name: appName,
      app_description: appDesc,
    })
      .replace(/\s+/g, " ")
      .trim();

    document.title = title;

    // Standard meta
    setMeta("name", "description", description);
    setMeta("name", "robots", "index, follow");
    setMeta("name", "theme-color", settings.primary_color || "#1E40AF");

    // Open Graph
    setMeta("property", "og:title", title);
    setMeta("property", "og:description", description);
    setMeta("property", "og:type", "website");
    setMeta("property", "og:site_name", appName);
    setMeta("property", "og:url", url);
    setMeta(
      "property",
      "og:locale",
      i18n.language === "en" ? "en_US" : "fr_FR",
    );
    if (settings.app_logo) {
      setMeta("property", "og:image", new URL(settings.app_logo, origin).href);
    }

    // Twitter Card
    setMeta("name", "twitter:card", "summary");
    setMeta("name", "twitter:title", title);
    setMeta("name", "twitter:description", description);

    // Canonical
    setCanonical(url);

    // JSON-LD structured data
    setJsonLd({
      "@context": "https://schema.org",
      "@type": "WebPage",
      name: title,
      description,
      url,
      isPartOf: {
        "@type": "WebApplication",
        name: appName,
        url: origin,
        ...(appDesc ? { description: appDesc } : {}),
      },
    });

    return () => {
      document.title = appName;
    };
  }, [settings, page, t, i18n.language]);

  return null;
}
