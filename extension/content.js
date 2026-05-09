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

  // Resolve an input's effective label text from every place forms put
  // it: <label for>, aria-label, aria-labelledby pointing at one or
  // more elements, placeholder, name, id. Returned text is lowercase
  // and whitespace-collapsed.
  function fieldLabelText(el) {
    const parts = [];
    if (el.labels && el.labels.length) {
      for (const l of el.labels) parts.push(l.textContent || "");
    }
    parts.push(el.getAttribute("aria-label") || "");
    const labelledBy = el.getAttribute("aria-labelledby");
    if (labelledBy) {
      for (const id of labelledBy.split(/\s+/)) {
        const ref = id && document.getElementById(id);
        if (ref) parts.push(ref.textContent || "");
      }
    }
    parts.push(el.getAttribute("placeholder") || "");
    parts.push(el.getAttribute("name") || "");
    parts.push(el.getAttribute("id") || "");
    return parts.join(" ").replace(/\s+/g, " ").toLowerCase().trim();
  }

  function isFillable(el) {
    if (!el || el.disabled || el.readOnly) return false;
    const type = (el.getAttribute("type") || "").toLowerCase();
    if (["hidden", "submit", "button", "file", "checkbox", "radio"].includes(type)) {
      return false;
    }
    // Skip elements that are visually hidden — most ATS use display:none
    // for stale duplicate inputs. We don't want to fill those.
    const cs = window.getComputedStyle(el);
    if (cs.display === "none" || cs.visibility === "hidden") return false;
    return true;
  }

  // Find the best matching input for a list of candidate label
  // substrings. Prefers untouched fields, falls back to any match
  // (so re-clicking Autofill still works after typing). Pass a
  // pre-filtered `candidates` list (e.g. only <textarea>s) to scope
  // the search.
  function findField(labels, candidates) {
    const els = candidates || Array.from(
      document.querySelectorAll("input, textarea, select")
    );
    let fallback = null;
    for (const el of els) {
      if (!isFillable(el)) continue;
      const txt = fieldLabelText(el);
      if (!labels.some((c) => txt.includes(c))) continue;
      if (!el.value) return el;
      if (!fallback) fallback = el;
    }
    return fallback;
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

  // Inject the highlight keyframe once — the autofill bar uses it to
  // briefly outline filled fields so the user can spot them.
  function ensureHighlightStyle() {
    if (document.getElementById("jobhunt-highlight-style")) return;
    const s = document.createElement("style");
    s.id = "jobhunt-highlight-style";
    s.textContent =
      "@keyframes jh-flash{" +
      "0%{box-shadow:0 0 0 0 rgba(15,118,110,.0)}" +
      "30%{box-shadow:0 0 0 4px rgba(15,118,110,.45)}" +
      "100%{box-shadow:0 0 0 0 rgba(15,118,110,0)}}" +
      ".jh-filled{animation:jh-flash 1.4s ease-out 1}";
    document.head.appendChild(s);
  }

  function flashField(el) {
    ensureHighlightStyle();
    el.classList.add("jh-filled");
    setTimeout(() => el.classList.remove("jh-filled"), 1500);
  }

  function autofill(pkg) {
    if (!pkg || !pkg.profile) return { filled: [], skipped: [] };
    const p = pkg.profile;
    const summary = pkg.resume_summary?.summary || null;
    const linkBy = (kind) =>
      (p.links || []).find((l) => l.kind === kind)?.url || "";
    const firstName = (p.name || "").split(" ")[0];
    const lastName = (p.name || "").split(" ").slice(1).join(" ");

    // Each entry: { name (display), labels (match candidates), value }
    const fields = [
      { name: "First name",   labels: ["first name", "firstname", "given name"], value: firstName },
      { name: "Last name",    labels: ["last name", "lastname", "surname", "family name"], value: lastName },
      { name: "Full name",    labels: ["full name", "your name"], value: p.name },
      { name: "Email",        labels: ["email"], value: p.email },
      { name: "Phone",        labels: ["phone", "mobile", "contact number"], value: p.phone },
      { name: "Location",     labels: ["location", "city", "address"], value: p.location },
      { name: "LinkedIn",     labels: ["linkedin"], value: linkBy("linkedin") },
      { name: "GitHub",       labels: ["github"], value: linkBy("github") },
      { name: "Portfolio",    labels: ["portfolio", "personal website", "website"], value: linkBy("portfolio") },
      { name: "Current title",   labels: ["current title", "current role", "job title", "current position"], value: p.current_title },
      { name: "Current employer", labels: ["current employer", "current company", "company name"], value: p.current_company },
      // Only fill the summary into a textarea labelled "about you" /
      // "tell us about yourself". A cover-letter textarea should be
      // tailored per-job, not generic — leave those alone.
      { name: "Summary",      labels: ["about you", "tell us about yourself", "professional summary", "bio"], value: summary, textareaOnly: true },
    ];

    const filled = [];
    const skipped = [];
    for (const f of fields) {
      if (!f.value) { skipped.push({ name: f.name, reason: "no value" }); continue; }
      const candidates = f.textareaOnly
        ? Array.from(document.querySelectorAll("textarea"))
        : undefined;
      const el = findField(f.labels, candidates);
      if (!el) { skipped.push({ name: f.name, reason: "no match" }); continue; }
      const original = el.value;
      setValue(el, f.value);
      flashField(el);
      filled.push({ name: f.name, value: f.value, el, original });
    }
    return { filled, skipped };
  }

  // ── Inject the floating action bar (Save + Autofill + status) ──────
  function mountActionBar() {
    if (document.getElementById("jobhunt-bar")) return;
    const family = detectAtsFamily();
    if (!family) return;

    let lastFill = null;  // { filled: [...], skipped: [...] } — for undo + status pane

    const bar = document.createElement("div");
    bar.id = "jobhunt-bar";
    bar.style.cssText =
      "position:fixed;bottom:16px;right:16px;z-index:2147483647;" +
      "background:#0f766e;color:#fff;padding:10px 12px;border-radius:8px;" +
      "font:12px/1.35 system-ui;box-shadow:0 6px 16px rgba(0,0,0,.18);" +
      "display:flex;flex-direction:column;gap:6px;max-width:340px";

    const headerRow = document.createElement("div");
    headerRow.style.cssText = "display:flex;gap:8px;align-items:center";

    const label = document.createElement("span");
    label.style.cssText = "font-weight:600";
    label.textContent = "JobHunt · " + family;
    headerRow.appendChild(label);

    const note = document.createElement("span");
    note.textContent = "never auto-submits";
    note.style.cssText = "opacity:.75;font-size:11px;margin-left:auto";
    headerRow.appendChild(note);

    bar.appendChild(headerRow);

    const buttonRow = document.createElement("div");
    buttonRow.style.cssText = "display:flex;gap:6px";

    const fillBtn = document.createElement("button");
    fillBtn.textContent = "Autofill";
    fillBtn.style.cssText =
      "background:#fff;color:#0f766e;border:0;padding:6px 10px;" +
      "border-radius:6px;font-weight:600;cursor:pointer;font:12px system-ui;flex:1";

    const saveBtn = document.createElement("button");
    saveBtn.textContent = "Save job";
    saveBtn.style.cssText =
      "background:rgba(255,255,255,.18);color:#fff;border:1px solid rgba(255,255,255,.45);" +
      "padding:6px 10px;border-radius:6px;font-weight:600;cursor:pointer;font:12px system-ui;flex:1";

    buttonRow.appendChild(fillBtn);
    buttonRow.appendChild(saveBtn);
    bar.appendChild(buttonRow);

    const status = document.createElement("div");
    status.style.cssText =
      "font-size:11px;color:#e6fffa;min-height:0;display:none";
    bar.appendChild(status);

    function showStatus(html) {
      status.style.display = "block";
      status.innerHTML = html;
    }

    // Undo button only renders inside the status pane after a fill.
    function renderFillStatus(result) {
      const { filled } = result;
      if (filled.length === 0) {
        showStatus("No matching fields found on this page.");
        return;
      }
      const list = filled.map((f) => `· ${f.name}`).join("<br>");
      showStatus(
        `<div><b>Filled ${filled.length}</b> field${filled.length === 1 ? "" : "s"} — review then submit</div>` +
        `<details style="margin-top:4px"><summary style="cursor:pointer;opacity:.85">Show fields</summary>` +
        `<div style="margin-top:4px">${list}</div></details>` +
        `<button id="jh-undo" style="margin-top:6px;background:transparent;color:#fff;border:1px solid rgba(255,255,255,.5);padding:3px 8px;border-radius:4px;cursor:pointer;font:11px system-ui">Undo fill</button>`
      );
      const undo = status.querySelector("#jh-undo");
      if (undo) undo.addEventListener("click", () => {
        for (const f of filled) {
          try { setValue(f.el, f.original); } catch { /* element may have unmounted */ }
        }
        showStatus("Undone — fields restored.");
        lastFill = null;
      });
    }

    fillBtn.addEventListener("click", () => {
      showStatus("Fetching profile…");
      chrome.runtime.sendMessage(
        { type: "fetch_application_package", url: location.href },
        (res) => {
          if (!res?.ok) {
            showStatus(`Error: ${res?.error ?? "unknown"}`);
            return;
          }
          if (!res.package?.profile) {
            showStatus("Profile not set up yet — open JobHunt and add one.");
            return;
          }
          const result = autofill(res.package);
          lastFill = result;
          renderFillStatus(result);
        }
      );
    });

    saveBtn.addEventListener("click", () => {
      saveBtn.disabled = true;
      saveBtn.textContent = "Saving…";
      const payload = (typeof extractJobFromPage === "function")
        ? extractJobFromPage()
        : { apply_url: location.href, title: document.title, company: "(unknown)" };
      chrome.runtime.sendMessage(
        { type: "save_job_url", payload },
        (res) => {
          saveBtn.disabled = false;
          if (res?.ok) {
            saveBtn.textContent = res.job?.duplicate ? "Already saved" : "Saved ✓";
            showStatus(
              `Saved as job #${res.job?.id}. ` +
              `<a href="http://localhost:3000/jobs/${res.job?.id}" target="_blank" style="color:#fff;text-decoration:underline">Open in JobHunt</a>`
            );
            setTimeout(() => { saveBtn.textContent = "Save job"; }, 3000);
          } else {
            saveBtn.textContent = "Save job";
            showStatus(`Save failed: ${res?.error ?? "unknown"}`);
          }
        }
      );
    });

    document.body.appendChild(bar);
  }

  // ── In-page scoring overlay (v2 primary surface) ────────────────────
  //
  // Auto-mounts a small floating button on supported job pages.
  // Click → extract JD → POST /extension/score → expand to full panel
  // with fit / trust / knockouts. User can then Save & tailor (deep-
  // links to the web app's package page) or close.
  //
  // Initial state is a small pill so we don't shout — the user opts
  // into scoring (which costs Anthropic tokens) by clicking.

  const BACKEND = "http://localhost:8000";
  const APP = "http://localhost:3000";

  function looksLikeJobPage() {
    if (!detectAtsFamily()) return false;
    // Heuristic: extracted description longer than 200 chars is a
    // good proxy for "this is a JD page" vs landing/search.
    const j = extractJobFromPage();
    return (j.description_md || "").length > 200;
  }

  function el(tag, style, text) {
    const e = document.createElement(tag);
    if (style) e.style.cssText = style;
    if (text != null) e.textContent = text;
    return e;
  }

  function row(...children) {
    const r = el("div", "display:flex;gap:6px;align-items:center;flex-wrap:wrap");
    for (const c of children) r.appendChild(c);
    return r;
  }

  const VERDICT_COLORS = {
    strong: ["#15803d", "#dcfce7"],
    good: ["#1e40af", "#dbeafe"],
    stretch: ["#a16207", "#fef3c7"],
    below: ["#525252", "#f5f5f5"],
    mismatch: ["#b91c1c", "#fee2e2"],
  };
  const TRUST_COLORS = {
    suspicious: ["#a16207", "#fef3c7"],
    likely_scam: ["#b91c1c", "#fee2e2"],
  };

  function badge(text, fg, bg) {
    return el(
      "span",
      `display:inline-flex;padding:2px 8px;border-radius:999px;` +
        `font:600 11px system-ui;color:${fg};background:${bg}`,
      text
    );
  }

  function mountScoringOverlay() {
    if (document.getElementById("jh-score-root")) return;
    if (!looksLikeJobPage()) return;

    const root = el(
      "div",
      "position:fixed;top:80px;right:16px;z-index:2147483647;" +
        "width:340px;background:#fafaf9;color:#0a0a0a;" +
        "border:1px solid #e5e5e5;border-radius:10px;" +
        "box-shadow:0 8px 24px rgba(0,0,0,.12);" +
        "font:13px system-ui;overflow:hidden"
    );
    root.id = "jh-score-root";

    // Header (always visible)
    const header = el(
      "div",
      "display:flex;justify-content:space-between;align-items:center;" +
        "padding:10px 14px;background:#0f766e;color:#fff"
    );
    const headerLeft = el("span", "font-weight:600", "JobHunt");
    const headerSub = el("span", "opacity:.8;font-size:11px;margin-left:6px",
      detectAtsFamily() || "");
    headerLeft.appendChild(headerSub);

    const closeBtn = el("button",
      "background:transparent;color:#fff;border:0;cursor:pointer;" +
        "font:600 16px system-ui;padding:0 4px;line-height:1",
      "✕");
    closeBtn.addEventListener("click", () => root.remove());

    header.appendChild(headerLeft);
    header.appendChild(closeBtn);
    root.appendChild(header);

    // Body
    const body = el("div", "padding:12px 14px");
    root.appendChild(body);

    // Initial state: prompt + score button
    function renderInitial() {
      body.replaceChildren();
      body.appendChild(el("p",
        "margin:0 0 8px 0;color:#525252;font-size:12px",
        "Score this job against your profile?"));
      body.appendChild(el("p",
        "margin:0 0 12px 0;color:#737373;font-size:11px",
        "Runs fit + trust check. Costs ~₹1-3 of Anthropic spend. Nothing persists unless you save."));
      const btn = el("button",
        "background:#0f766e;color:#fff;border:0;padding:8px 14px;" +
          "border-radius:6px;font:600 12px system-ui;cursor:pointer;width:100%",
        "Score this job");
      btn.addEventListener("click", () => void runScore());
      body.appendChild(btn);
    }

    function renderLoading(msg) {
      body.replaceChildren();
      body.appendChild(el("p",
        "margin:0;color:#525252;font-size:12px",
        msg));
    }

    function renderError(msg) {
      body.replaceChildren();
      body.appendChild(el("p",
        "margin:0 0 10px 0;color:#b91c1c;font-size:12px",
        msg));
      const retry = el("button",
        "background:#fff;color:#0a0a0a;border:1px solid #e5e5e5;" +
          "padding:6px 10px;border-radius:6px;font:600 12px system-ui;cursor:pointer",
        "Retry");
      retry.addEventListener("click", () => void runScore());
      body.appendChild(retry);
    }

    function renderScored(payload, score) {
      body.replaceChildren();

      // Fit
      if (score.fit) {
        const [fg, bg] = VERDICT_COLORS[score.fit.verdict] || ["#525252", "#f5f5f5"];
        const fitRow = el("div", "margin-bottom:10px");
        fitRow.appendChild(el("div",
          "display:flex;align-items:center;gap:8px;margin-bottom:4px",
          ""));
        fitRow.firstChild.appendChild(el("span", "font-weight:600;font-size:11px;color:#737373", "FIT"));
        fitRow.firstChild.appendChild(badge(score.fit.verdict, fg, bg));
        if (score.fit.skills_match_json?.score_required) {
          fitRow.firstChild.appendChild(el("span",
            "color:#737373;font-size:11px",
            score.fit.skills_match_json.score_required));
        }
        fitRow.appendChild(el("p",
          "margin:0;color:#0a0a0a;font-size:12px;line-height:1.4",
          score.fit.summary_md || ""));
        body.appendChild(fitRow);
      } else {
        const note = el("div",
          "margin-bottom:10px;padding:8px;background:#fef3c7;border-radius:6px;" +
            "font-size:11px;color:#a16207");
        note.textContent = score.notes?.[0] || "Set up your profile to enable fit scoring.";
        body.appendChild(note);
      }

      // Trust
      if (score.trust) {
        const trustRow = el("div", "margin-bottom:10px");
        const trustHead = el("div", "display:flex;align-items:center;gap:8px;margin-bottom:4px");
        trustHead.appendChild(el("span", "font-weight:600;font-size:11px;color:#737373", "TRUST"));
        const tc = TRUST_COLORS[score.trust.verdict];
        if (tc) {
          trustHead.appendChild(badge(`⚠ ${score.trust.verdict.replace("_", " ")}`, tc[0], tc[1]));
        } else {
          trustHead.appendChild(badge("✓ no flags", "#15803d", "#dcfce7"));
        }
        trustRow.appendChild(trustHead);
        if (score.trust.scam_signals_json?.length || score.trust.ghost_job_signals_json?.length) {
          const ul = el("ul", "margin:4px 0 0 0;padding-left:18px;font-size:11px;color:#525252");
          for (const s of (score.trust.scam_signals_json || []).slice(0, 3)) {
            ul.appendChild(el("li", "margin:2px 0", s.description));
          }
          for (const s of (score.trust.ghost_job_signals_json || []).slice(0, 2)) {
            ul.appendChild(el("li", "margin:2px 0", s.description));
          }
          trustRow.appendChild(ul);
        }
        body.appendChild(trustRow);
      }

      // Knockouts
      if (score.knockouts?.length) {
        const koRow = el("div", "margin-bottom:10px");
        koRow.appendChild(el("div",
          "font-weight:600;font-size:11px;color:#737373;margin-bottom:4px",
          "KNOCKOUTS"));
        const ul = el("ul", "margin:0;padding-left:18px;font-size:11px;color:#525252");
        for (const k of score.knockouts.slice(0, 4)) {
          ul.appendChild(el("li", "margin:2px 0", k.question_text));
        }
        koRow.appendChild(ul);
        body.appendChild(koRow);
      }

      // Actions
      const actions = el("div", "display:flex;gap:6px;margin-top:8px");
      const tailorBtn = el("button",
        "flex:1;background:#0f766e;color:#fff;border:0;padding:8px;" +
          "border-radius:6px;font:600 12px system-ui;cursor:pointer",
        "Save & tailor");
      tailorBtn.addEventListener("click", () => void runSaveAndTailor(payload));
      actions.appendChild(tailorBtn);

      const saveBtn = el("button",
        "background:#fff;color:#0a0a0a;border:1px solid #e5e5e5;" +
          "padding:8px 12px;border-radius:6px;font:600 12px system-ui;cursor:pointer",
        "Just save");
      saveBtn.addEventListener("click", () => void runJustSave(payload));
      actions.appendChild(saveBtn);
      body.appendChild(actions);
    }

    function renderSaved(result, kind) {
      body.replaceChildren();
      body.appendChild(el("p",
        "margin:0 0 10px 0;color:#15803d;font-size:13px;font-weight:600",
        "✓ " + (kind === "tailor" ? "Saved." : "Saved (no tailoring).")));
      if (kind === "tailor" && result.tailoring_status !== "kicked_off") {
        body.appendChild(el("p",
          "margin:0 0 10px 0;color:#a16207;font-size:11px;background:#fef3c7;padding:8px;border-radius:6px",
          result.tailoring_status === "skipped_no_profile"
            ? "Set up your profile in JobHunt to enable tailoring."
            : "Upload a master resume in JobHunt to enable tailoring."));
      }
      const link = el("a",
        "display:block;text-align:center;background:#0f766e;color:#fff;" +
          "padding:8px;border-radius:6px;font:600 12px system-ui;" +
          "text-decoration:none",
        kind === "tailor" ? "Open package in JobHunt" : "Open in JobHunt");
      link.href = kind === "tailor"
        ? result.package_url
        : `${APP}/jobs/${result.id}`;
      link.target = "_blank";
      link.rel = "noopener noreferrer";
      body.appendChild(link);
    }

    async function runScore() {
      const payload = extractJobFromPage();
      if (!payload.description_md) {
        renderError("Couldn't read the job description. Page may be loading.");
        return;
      }
      renderLoading("Scoring… ~5-10 sec.");
      try {
        const res = await fetch(`${BACKEND}/extension/score`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        });
        if (!res.ok) {
          const text = await res.text();
          renderError(`Backend error ${res.status}: ${text.slice(0, 100)}`);
          return;
        }
        const score = await res.json();
        renderScored(payload, score);
      } catch (err) {
        renderError("Couldn't reach JobHunt at localhost:8000. Is the backend running?");
      }
    }

    async function runSaveAndTailor(payload) {
      renderLoading("Saving…");
      try {
        const res = await fetch(`${BACKEND}/extension/save-and-tailor`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        });
        if (!res.ok) {
          renderError(`Save failed: ${res.status}`);
          return;
        }
        renderSaved(await res.json(), "tailor");
      } catch (err) {
        renderError("Couldn't reach JobHunt backend.");
      }
    }

    async function runJustSave(payload) {
      renderLoading("Saving…");
      try {
        const res = await fetch(`${BACKEND}/extension/save-job`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        });
        if (!res.ok) {
          renderError(`Save failed: ${res.status}`);
          return;
        }
        renderSaved(await res.json(), "save");
      } catch (err) {
        renderError("Couldn't reach JobHunt backend.");
      }
    }

    renderInitial();
    document.body.appendChild(root);
  }

  function mountAll() {
    mountActionBar();
    mountScoringOverlay();
  }

  if (document.readyState === "complete" || document.readyState === "interactive") {
    mountAll();
  } else {
    window.addEventListener("DOMContentLoaded", mountAll);
  }

  // SPAs (LinkedIn / Naukri / Wellfound) navigate without a full page
  // load. Watch URL changes and re-mount.
  let lastHref = location.href;
  setInterval(() => {
    if (location.href !== lastHref) {
      lastHref = location.href;
      const existing = document.getElementById("jh-score-root");
      if (existing) existing.remove();
      // Wait a tick for the SPA to paint
      setTimeout(mountAll, 1500);
    }
  }, 1000);
})();
