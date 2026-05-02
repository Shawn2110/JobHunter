// JobHunt content script. Detects ATS application forms and offers
// autofill. NEVER calls form.submit() or clicks submit buttons.
// Per Agent.md § 2 — the user reviews and clicks submit, every time.

(function () {
  "use strict";

  function detectAtsFamily() {
    const host = location.hostname.toLowerCase();
    if (host.includes("myworkdayjobs.com")) return "workday";
    if (host.includes("greenhouse.io")) return "greenhouse";
    if (host.includes("lever.co")) return "lever";
    if (host.includes("ashbyhq.com")) return "ashby";
    if (host.includes("icims.com")) return "icims";
    if (host.includes("smartrecruiters.com")) return "smartrecruiters";
    return null;
  }

  function findField(labels) {
    // Match by associated label text or aria-label or placeholder.
    const inputs = Array.from(
      document.querySelectorAll("input, textarea, select")
    );
    for (const el of inputs) {
      const labelText = (
        (el.labels && el.labels[0] && el.labels[0].textContent) ||
        el.getAttribute("aria-label") ||
        el.getAttribute("placeholder") ||
        el.getAttribute("name") ||
        ""
      )
        .toLowerCase()
        .trim();
      for (const candidate of labels) {
        if (labelText.includes(candidate)) return el;
      }
    }
    return null;
  }

  function setValue(el, value) {
    if (!el || value == null) return;
    const proto = el.tagName === "TEXTAREA"
      ? HTMLTextAreaElement.prototype
      : HTMLInputElement.prototype;
    const setter = Object.getOwnPropertyDescriptor(proto, "value")?.set;
    if (setter) setter.call(el, value);
    else el.value = value;
    el.dispatchEvent(new Event("input", { bubbles: true }));
    el.dispatchEvent(new Event("change", { bubbles: true }));
  }

  function autofill(pkg) {
    if (!pkg || !pkg.profile) return { filled: 0 };
    const p = pkg.profile;
    const fields = [
      [["first name", "firstname", "given name"], (p.name || "").split(" ")[0]],
      [["last name", "lastname", "surname", "family name"], (p.name || "").split(" ").slice(1).join(" ")],
      [["full name"], p.name],
      [["email"], p.email],
      [["phone", "mobile"], p.phone],
      [["linkedin"], (p.links || []).find((l) => l.kind === "linkedin")?.url ?? ""],
      [["github"], (p.links || []).find((l) => l.kind === "github")?.url ?? ""],
      [["portfolio", "website"], (p.links || []).find((l) => l.kind === "portfolio")?.url ?? ""],
    ];
    let filled = 0;
    for (const [labels, value] of fields) {
      if (!value) continue;
      const el = findField(labels);
      if (el) {
        setValue(el, value);
        filled += 1;
      }
    }
    return { filled };
  }

  // ── Inject a tiny floating action bar ───────────────────────────────
  function mountActionBar() {
    if (document.getElementById("jobhunt-bar")) return;
    const family = detectAtsFamily();
    if (!family) return;

    const bar = document.createElement("div");
    bar.id = "jobhunt-bar";
    bar.style.cssText =
      "position:fixed;bottom:16px;right:16px;z-index:2147483647;" +
      "background:#0f766e;color:#fff;padding:10px 14px;border-radius:8px;" +
      "font:12px system-ui;box-shadow:0 6px 16px rgba(0,0,0,.18);" +
      "display:flex;gap:8px;align-items:center";

    const label = document.createElement("span");
    label.textContent = "JobHunt · " + family;
    bar.appendChild(label);

    const btn = document.createElement("button");
    btn.textContent = "Autofill";
    btn.style.cssText =
      "background:#fff;color:#0f766e;border:0;padding:6px 10px;" +
      "border-radius:6px;font-weight:600;cursor:pointer;font:12px system-ui";
    btn.addEventListener("click", () => {
      chrome.runtime.sendMessage(
        { type: "fetch_application_package", url: location.href },
        (res) => {
          if (!res?.ok) {
            label.textContent = "JobHunt · " + (res?.error ?? "error");
            return;
          }
          const r = autofill(res.package);
          label.textContent = `JobHunt · ${r.filled} field(s) filled — review then submit`;
        }
      );
    });
    bar.appendChild(btn);

    const note = document.createElement("span");
    note.textContent = "(never auto-submits)";
    note.style.cssText = "opacity:.75";
    bar.appendChild(note);

    document.body.appendChild(bar);
  }

  if (document.readyState === "complete" || document.readyState === "interactive") {
    mountActionBar();
  } else {
    window.addEventListener("DOMContentLoaded", mountActionBar);
  }
})();
