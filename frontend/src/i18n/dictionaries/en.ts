import type { Dictionary } from "./ar";

const en: Dictionary = {
  meta: {
    title: "Iraq PropTech — Smart Real Estate Platform",
    description: "An Iraqi platform to find, sell and rent property, with maps and AI analysis.",
  },
  nav: {
    home: "Home",
    properties: "Properties",
    map: "Map",
    login: "Sign in",
    switchLanguage: "العربية",
  },
  home: {
    badge: "In development",
    title: "The Iraqi real-estate platform",
    subtitle:
      "Buy, sell and rent property in Basra and across Iraq, with map search and AI analysis that never invents facts.",
    foundationNote:
      "This is a development build of the technical foundation. No real listings are shown yet.",
  },
  status: {
    heading: "System status",
    api: "API",
    database: "Database",
    postgis: "GIS (PostGIS)",
    redis: "Redis (background jobs)",
    ok: "Operational",
    degraded: "Degraded",
    error: "Down",
    unavailable: "Unavailable",
    notConfigured: "API URL is not configured",
  },
  errors: {
    NETWORK_ERROR: "Could not reach the server. Check your connection and try again.",
    NOT_FOUND: "We couldn't find what you were looking for.",
    NOT_AUTHENTICATED: "Please sign in to continue.",
    PERMISSION_DENIED: "You don't have permission to do that.",
    VALIDATION_ERROR: "Some of the information entered is invalid.",
    RATE_LIMITED: "Too many requests. Please wait a moment.",
    INTERNAL_ERROR: "Something went wrong on our side. We're on it.",
    UNKNOWN: "Something went wrong. Please try again later.",
  },
};

export default en;
