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
    if (host.includes("naukri.com")) return "naukri";
    if (host.includes("foundit.in")) return "foundit";
    if (host.includes("wellfound.com")) return "wellfound";
    return null;
  }

  // ── JD extraction (read-only DOM access — your logged-in session) ──
  //
  // For each portal, try a stack of selectors. First match wins; if
  // nothing matches, fall back to <h1> / <title> / page innerText.
  // Selectors break when portals redesign — keep them grouped per
  // portal so fixes are localized.

  function firstText(selectors) {
    for (const sel of selectors) {
      const el = document.querySelector(sel);
      const text = (el?.textContent || "").trim();
      if (text) return text;
    }
    return "";
  }

  function firstInnerText(selectors) {
    for (const sel of selectors) {
      const el = document.querySelector(sel);
      const text = (el?.innerText || "").trim();
      if (text && text.length > 50) return text;
    }
    return "";
  }

  const SELECTORS = {
    naukri: {
      title: ["h1.styles_jd-header-title__rZwM1", "h1[class*='jd-header']", "h1"],
      company: [
        ".styles_jd-header-comp-name__MvqAI",
        "[class*='comp-name']",
        "[data-test*='employer']",
      ],
      location: [".styles_jhc__location__W_OKu", "[class*='location']"],
      description: [
        ".styles_JDC__dang-inner-html__h0K4t",
        "section[class*='JDC'] [class*='dang-inner']",
        "section[class*='JD']",
      ],
    },
    greenhouse: {
      title: [".app-title", "h1.app-title", "h1"],
      company: [".company-name", "h2.company-name"],
      location: [".location"],
      description: ["#content", ".job__description"],
    },
    lever: {
      title: [".posting-headline h2", "h2"],
      company: [".main-header-text h1", "h1.main-header-text"],
      location: [".location"],
      description: [".posting-page section.section", ".section-page"],
    },
    ashby: {
      title: ["h1"],
      company: ["[class*='company-name']", "h2"],
      location: ["[class*='location']"],
      description: ["main", "[class*='description']"],
    },
    foundit: {
      title: ["h1", "[class*='jd-title']"],
      company: ["[class*='comp-name']", "[class*='company']"],
      location: ["[class*='location']"],
      description: ["[class*='description']", "section"],
    },
    wellfound: {
      title: ["h1", "h2"],
      company: ["[class*='company-name']", "h2 a"],
      location: ["[class*='location']"],
      description: ["[class*='description']", "main"],
    },
    workday: {
      title: ["[data-automation-id='jobPostingHeader']", "h2", "h1"],
      company: ["[data-automation-id='jobPostingCompany']"],
      location: ["[data-automation-id='locations']"],
      description: ["[data-automation-id='jobPostingDescription']"],
    },
  };

  function extractJobFromPage() {
    const family = detectAtsFamily();
    const sels = (family && SELECTORS[family]) || {};

    // Generic fallback selectors layered after portal-specific ones
    const titleSels = [...(sels.title || []), "h1", "title"];
    const companySels = [...(sels.company || []), "[class*='company']"];
    const locationSels = [...(sels.location || []), "[class*='location']"];
    const descSels = [...(sels.description || []), "main", "article"];

    const title = firstText(titleSels) || document.title || "(unknown)";
    const company = firstText(companySels) || "(unknown)";
    const locationText = firstText(locationSels) || null;
    const description = firstInnerText(descSels);

    return {
      portal: family || "generic",
      title,
      company,
      location: locationText,
      description_md: description ? description.slice(0, 16000) : null,
      apply_url: window.location.href,
    };
  }

  // Make available to popup via chrome.tabs.sendMessage
  chrome.runtime.onMessage.addListener((msg, _sender, sendResponse) => {
    if (msg?.type === "extract_job_from_page") {
      try {
        sendResponse({ ok: true, payload: extractJobFromPage() });
      } catch (err) {
        sendResponse({ ok: false, error: String(err) });
      }
      return true;
    }
    return false;
  });

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
