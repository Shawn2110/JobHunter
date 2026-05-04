import Link from "next/link";

const LINKS = [
  { href: "/", label: "Home" },
  { href: "/profile", label: "Profile" },
  { href: "/search", label: "Search" },
];

export function Nav() {
  return (
    <nav className="border-b border-neutral-200 bg-white">
      <div className="mx-auto flex max-w-6xl items-center gap-6 px-6 py-3">
        <div className="flex items-center gap-2">
          <span className="text-sm font-semibold tracking-tight">JobHunt</span>
          <span className="hidden rounded-full bg-teal-50 px-2 py-0.5 text-[10px] font-medium uppercase tracking-wider text-teal-700 sm:inline">
            extension is the main surface
          </span>
        </div>
        <ul className="flex items-center gap-4 text-sm text-neutral-600">
          {LINKS.map((l) => (
            <li key={l.href}>
              <Link
                href={l.href}
                className="rounded px-2 py-1 hover:bg-neutral-100 hover:text-neutral-900"
              >
                {l.label}
              </Link>
            </li>
          ))}
        </ul>
      </div>
    </nav>
  );
}
