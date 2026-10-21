import { Link, useRouterState } from "@tanstack/react-router";
import { Home, CalendarDays, LayoutGrid, Bookmark, User } from "lucide-react";
import { cn } from "@/lib/utils";

const items = [
  { to: "/", label: "Accueil", icon: Home, match: (p: string) => p === "/" },
  { to: "/calendrier", label: "Calendrier", icon: CalendarDays, match: (p: string) => p.startsWith("/calendrier") },
  { to: "/catalogue", label: "Catalogue", icon: LayoutGrid, center: true, match: (p: string) => p.startsWith("/catalogue") },
  { to: "/profile", label: "Ma Liste", icon: Bookmark, hash: "liste", match: () => false },
  { to: "/profile", label: "Profil", icon: User, match: (p: string) => p.startsWith("/profile") || p.startsWith("/auth") },
] as const;

/** Fixed mobile bottom navigation with a raised orange Catalogue button. */
export function BottomNav() {
  const pathname = useRouterState({ select: (s) => s.location.pathname });
  if (pathname.startsWith("/admin")) return null;

  return (
    <nav
      aria-label="Navigation principale"
      className="md:hidden fixed bottom-0 inset-x-0 z-50 border-t border-border bg-background/95 backdrop-blur-xl pb-[env(safe-area-inset-bottom)]"
    >
      <ul className="grid grid-cols-5 h-16">
        {items.map((it) => {
          const Icon = it.icon;
          const active = it.match(pathname);
          if ("center" in it && it.center) {
            return (
              <li key={it.label} className="flex justify-center">
                <Link
                  to={it.to}
                  aria-label={it.label}
                  className="-mt-6 flex flex-col items-center gap-1"
                >
                  <span
                    className={cn(
                      "w-14 h-14 rounded-full bg-primary text-primary-foreground flex items-center justify-center shadow-glow ring-4 ring-background transition-transform active:scale-95",
                      active && "scale-105",
                    )}
                  >
                    <Icon className="w-6 h-6" />
                  </span>
                  <span className={cn("text-[10px] font-semibold", active ? "text-primary" : "text-muted-foreground")}>
                    {it.label}
                  </span>
                </Link>
              </li>
            );
          }
          return (
            <li key={it.label}>
              <Link
                to={it.to}
                hash={"hash" in it ? it.hash : undefined}
                className={cn(
                  "h-full flex flex-col items-center justify-center gap-1 text-[10px] font-semibold transition-colors",
                  active ? "text-primary" : "text-muted-foreground hover:text-foreground",
                )}
              >
                <Icon className="w-5 h-5" />
                {it.label}
              </Link>
            </li>
          );
        })}
      </ul>
    </nav>
  );
}
