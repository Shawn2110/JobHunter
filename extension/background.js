// JobHunt service worker. Lightweight: just listens for content-script
// messages and proxies to the local backend. Never sends data anywhere
// other than http://localhost:8000.

const BACKEND = "http://localhost:8000";

chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
  if (msg?.type === "fetch_application_package") {
    fetch(`${BACKEND}/extension/application-package?url=${encodeURIComponent(msg.url ?? "")}`)
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error(`HTTP ${r.status}`))))
      .then((body) => sendResponse({ ok: true, package: body }))
      .catch((err) => sendResponse({ ok: false, error: String(err) }));
    return true; // async response
  }
  if (msg?.type === "save_job_url") {
    // Two payload shapes for back-compat:
    //   - new: { payload: {portal, title, company, location, description_md, apply_url} }
    //   - old: { url, title }
    const body = msg.payload
      ? msg.payload
      : { url: msg.url, title: msg.title ?? null };
    fetch(`${BACKEND}/extension/save-job`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    })
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error(`HTTP ${r.status}`))))
      .then((body) => sendResponse({ ok: true, job: body }))
      .catch((err) => sendResponse({ ok: false, error: String(err) }));
    return true;
  }
  return false;
});
