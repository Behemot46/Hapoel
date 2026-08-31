"use strict";

// Bump VERSION whenever the app shell changes. It names the caches, so a
// new version drops the old ones instead of serving them forever.
const VERSION = "v18";
const SHELL_CACHE = "shell-" + VERSION;
const DATA_CACHE = "data-" + VERSION;

const SHELL_FILES = [
  "./",
  "index.html",
  "css/style.css",
  "js/app.js",
  "manifest.webmanifest",
  "icons/crest.png",
  "icons/icon-192.png",
  "icons/icon-512.png",
];

self.addEventListener("install", e => {
  e.waitUntil(
    caches.open(SHELL_CACHE)
      // reload bypasses the HTTP cache so a fresh install really is fresh
      .then(c => c.addAll(SHELL_FILES.map(u => new Request(u, { cache: "reload" }))))
      .then(() => self.skipWaiting())
  );
});

self.addEventListener("activate", e => {
  e.waitUntil(
    caches.keys()
      .then(keys => Promise.all(
        keys.filter(k => k !== SHELL_CACHE && k !== DATA_CACHE).map(k => caches.delete(k))
      ))
      .then(() => self.clients.claim())
  );
});

// Network first, cache as fallback. Being a day-to-day app, showing the
// current schedule matters more than shaving milliseconds off a load, and
// cache-first was pinning returning fans to whatever version they saw first.
self.addEventListener("fetch", e => {
  const url = new URL(e.request.url);
  if (e.request.method !== "GET" || url.origin !== location.origin) return;

  // the live score is meaningful only while it is fresh, and it is polled
  // with a cache-buster, caching it would both mislead and fill the store
  if (url.pathname.endsWith("/live.json")) return;

  const cacheName = url.pathname.includes("/data/") ? DATA_CACHE : SHELL_CACHE;

  e.respondWith(
    fetch(e.request)
      .then(res => {
        if (res && res.ok) {
          const copy = res.clone();
          caches.open(cacheName).then(c => c.put(e.request, copy));
        }
        return res;
      })
      .catch(() => caches.match(e.request).then(hit =>
        // an offline navigation to any route should still open the app
        hit || (e.request.mode === "navigate" ? caches.match("index.html") : undefined)
      ))
  );
});
