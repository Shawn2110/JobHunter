document.getElementById("save").addEventListener("click", async () => {
  const tab = (await chrome.tabs.query({ active: true, currentWindow: true }))[0];
  if (!tab) return;
  chrome.runtime.sendMessage(
    { type: "save_job_url", url: tab.url, title: tab.title },
    (res) => {
      const status = document.getElementById("status");
      status.textContent = res?.ok
        ? "Saved (local only)"
        : `Failed: ${res?.error ?? "unknown error"}`;
    }
  );
});

document.getElementById("open").addEventListener("click", () => {
  chrome.tabs.create({ url: "http://localhost:3000" });
});
