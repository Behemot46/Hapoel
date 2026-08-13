"use strict";

const SHELL_CACHE = "shell-v1";
const DATA_CACHE = "data-v1";
const SHELL_FILES = [
  "./",
  "index.html",
  "css/style.css",
  "js/app.js",
  "manifest.webmanifest",
  "icons/icon-192.png",
  "icons/icon-512.png",
];

self.addEventListener("install", e => {
  e.waitUntil(caches.open(SHELL_CACHE).then(c => c.addAll(SHELL_FILES)).then(() => self.skipWaiting()));
});

self.addEventListener("activate", e => {
  e.waitUntil(
    caches.keys().then(keys =>
      Promise.all(keys.filter(k => k !== SHELL_CACHE && k !== DATA_CACHE).map(k => caches.delete(k)))
    ).then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", e => {
  const url = new URL(e.request.url);
  if (e.request.method !== "GET" || url.origin !== location.origin) return;

  if (url.pathname.includes("/data/")) {
    // Data: fresh when online, cached copy offline
    e.respondWith(
      fetch(e.request)
        .then(res => {
          const copy = res.clone();
          caches.open(DATA_CACHE).then(c => c.put(e.request, copy));
          return res;
        })
        .catch(() => caches.match(e.request))
    );
    return;
  }

  // Shell: cache first
  e.respondWith(
    caches.match(e.request).then(hit => hit ||
      fetch(e.request).then(res => {
        const copy = res.clone();
        caches.open(SHELL_CACHE).then(c => c.put(e.request, copy));
        return res;
      })
    )
  );
});
