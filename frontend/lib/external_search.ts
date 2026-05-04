/**
 * URL builders for "search elsewhere" deep-link buttons.
 *
 * Pure templates — no HTTP calls, no portal data fetched. The user
 * clicks a button, the portal's native search page opens in a new
 * tab in the user's logged-in browser session. Per ADR 0006, this is
 * the v1 launcher pattern: portals do the search, JobHunt is the
 * launcher.
 */

import type { SearchInput } from "@/lib/api";

export interface ExternalPortal {
  id: string;
  label: string;
  description: string;
  buildUrl: (input: SearchInput) => string;
}

function slug(s: string): string {
  return s
    .toLowerCase()
    .trim()
    .replace(/[^a-z0-9\s-]/g, "")
    .replace(/\s+/g, "-")
    .replace(/-+/g, "-");
}

function locationParam(input: SearchInput): string {
  return input.locations?.[0] ?? "";
}

export const EXTERNAL_PORTALS: ExternalPortal[] = [
  {
    id: "linkedin",
    label: "LinkedIn",
    description: "Largest professional network",
    buildUrl: (input) => {
      const params = new URLSearchParams({
        keywords: input.role,
        location: locationParam(input),
      });
      // f_WT: 1 onsite, 2 remote, 3 hybrid
      if (input.work_mode === "remote") params.set("f_WT", "2");
      else if (input.work_mode === "hybrid") params.set("f_WT", "3");
      else if (input.work_mode === "onsite") params.set("f_WT", "1");
      return `https://www.linkedin.com/jobs/search/?${params.toString()}`;
    },
  },
  {
    id: "naukri",
    label: "Naukri",
    description: "India's largest job portal",
    buildUrl: (input) => {
      const roleSlug = slug(input.role || "jobs");
      const locSlug = slug(locationParam(input));
      const path = locSlug
        ? `${roleSlug}-jobs-in-${locSlug}`
        : `${roleSlug}-jobs`;
      return `https://www.naukri.com/${path}`;
    },
  },
  {
    id: "indeed",
    label: "Indeed",
    description: "Large global aggregator (India region)",
    buildUrl: (input) => {
      const params = new URLSearchParams({
        q: input.role,
        l: locationParam(input),
      });
      if (input.work_mode === "remote") {
        // Indeed's remote filter — encoded query
        params.set("sc", "0kf:attr(DSQF7);");
      }
      return `https://in.indeed.com/jobs?${params.toString()}`;
    },
  },
  {
    id: "foundit",
    label: "Foundit",
    description: "Formerly Monster India",
    buildUrl: (input) => {
      const params = new URLSearchParams({
        query: input.role,
        locations: locationParam(input),
      });
      return `https://www.foundit.in/srp/results?${params.toString()}`;
    },
  },
  {
    id: "wellfound",
    label: "Wellfound",
    description: "Startup-focused (formerly AngelList)",
    buildUrl: (input) => {
      const params = new URLSearchParams({
        keywords: input.role,
        location: locationParam(input),
      });
      return `https://wellfound.com/jobs?${params.toString()}`;
    },
  },
  {
    id: "glassdoor",
    label: "Glassdoor",
    description: "Salary + company reviews",
    buildUrl: (input) => {
      const params = new URLSearchParams({
        "sc.keyword": input.role,
        locT: "C",
        locKeyword: locationParam(input),
      });
      return `https://www.glassdoor.co.in/Job/jobs.htm?${params.toString()}`;
    },
  },
  {
    id: "hackernews",
    label: "HN Who's Hiring",
    description: "Founder-driven monthly thread",
    buildUrl: (input) => {
      const params = new URLSearchParams({
        q: `${input.role} ${locationParam(input)}`.trim(),
        type: "comment",
        sort: "byPopularity",
      });
      // Algolia search across HN comments — most matches will be in
      // the latest "Who is hiring" thread.
      return `https://hn.algolia.com/?${params.toString()}`;
    },
  },
];
