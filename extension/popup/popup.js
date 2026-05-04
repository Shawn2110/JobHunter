// Popup save flow:
//   1. Ask the active tab's content script to extract a rich JD payload.
//   2. Fall back to URL + title from chrome.tabs if extraction fails
//      (e.g., tab is on an unsupported portal where the content script
//      didn't inject).
//   3. Send to the local backend via the background service worker.

async function getActiveTab() {
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  return tab ?? null;
}

async function extractFromTab(tab) {
  // chrome.tabs.sendMessage throws if no content script is listening
  // on the target tab. We catch and fall through to a URL-only save.
  try {
    return await chrome.tabs.sendMessage(tab.id, {
      type: "extract_job_from_page",
    });
  } catch {
    return null;
  }
}

document.getElementById("save").addEventListener("click", async () => {
  const status = document.getElementById("status");
  status.textContent = "Reading page…";

  const tab = await getActiveTab();
  if (!tab) {
    status.textContent = "No active tab.";
    return;
  }

  const extracted = await extractFromTab(tab);
  let payload;
  if (extracted?.ok && extracted.payload) {
    // Rich payload from content script
    payload = { ...extracted.payload, apply_url: tab.url ?? extracted.payload.apply_url };
  } else {
    // Fallback — content script didn't run on this page
    payload = {
      portal: "unsupported",
      title: tab.title || "(saved)",
      company: "(unknown)",
      location: null,
      description_md: null,
      apply_url: tab.url,
    };
  }

  status.textContent = "Saving…";
  chrome.runtime.sendMessage(
    { type: "save_job_url", payload },
    (res) => {
      if (res?.ok) {
        const job = res.job;
        const richness = payload.description_md ? "rich" : "URL only";
        status.innerHTML = `Saved (${richness}). <a href="http://localhost:3000/jobs/${job.id}" target="_blank">Open in JobHunt</a>`;
      } else {
        status.textContent = `Failed: ${res?.error ?? "unknown error"}`;
      }
    }
  );
});

document.getElementById("open").addEventListener("click", () => {
  chrome.tabs.create({ url: "http://localhost:3000" });
});
