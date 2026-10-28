/*
 * SHELF starter service worker.
 *
 * This is intentionally small and dependency-free. It caches the launch shell
 * and static assets, then serves navigations from the network first.
 *
 * IMPORTANT FOR THE APP DEVELOPER:
 * - Bump CACHE_VERSION on every production deploy.
 * - Add the app's build output (JS/CSS) to CORE_ASSETS if it is generated ahead
 *   of time. Unknown static requests are cached after their first fetch, so an
 *   installed app still works offline after one successful online visit.
 * - Do not cache API responses here. Requests with destination "" (fetch/XHR)
 *   pass through untouched.
 */
const CACHE_PREFIX = "shelf-shell-";
const CACHE_VERSION = CACHE_PREFIX + "v1";

const CORE_ASSETS = [
  "./",
  "./index.html",
  "./manifest.webmanifest",
  "./launch/splash-critical.css",
  "./launch/shelf-splash.js",
  "./icons/icon-192.png",
  "./icons/icon-512.png",
  "./icons/maskable-512.png",
  "./icons/apple-touch-icon-180.png",
  "./icons/favicon-32.png",
  "./icons/favicon-16.png"
];

self.addEventListener("install", event => {
  event.waitUntil((async () => {
    const cache = await caches.open(CACHE_VERSION);
    await cache.addAll(CORE_ASSETS);
    await self.skipWaiting();
  })());
});

self.addEventListener("activate", event => {
  event.waitUntil((async () => {
    const keys = await caches.keys();
    await Promise.all(
      keys
        .filter(key => key.startsWith(CACHE_PREFIX) && key !== CACHE_VERSION)
        .map(key => caches.delete(key))
    );
    await self.clients.claim();
  })());
});

self.addEventListener("fetch", event => {
  const request = event.request;
  if (request.method !== "GET") return;

  const url = new URL(request.url);
  if (url.origin !== self.location.origin) return;

  if (request.mode === "navigate") {
    event.respondWith(networkFirst(request));
    return;
  }

  if (["style", "script", "image", "font", "manifest"].includes(request.destination)) {
    event.respondWith(staleWhileRevalidate(request));
  }
});

async function networkFirst(request) {
  const cache = await caches.open(CACHE_VERSION);
  try {
    const response = await fetch(request);
    if (response.ok) cache.put(request, response.clone());
    return response;
  } catch (error) {
    const cached = await cache.match(request, { ignoreSearch: true });
    if (cached) return cached;
    return (await cache.match("./index.html")) || Response.error();
  }
}

async function staleWhileRevalidate(request) {
  const cache = await caches.open(CACHE_VERSION);
  const cached = await cache.match(request);

  const network = fetch(request)
    .then(response => {
      if (response.ok) cache.put(request, response.clone());
      return response;
    })
    .catch(() => Response.error());

  return cached || network;
}
