import { Link, NavLink, Navigate, Outlet, useLocation } from "react-router-dom";
import { useState, type ReactNode } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  LayoutDashboard,
  Film,
  FolderOpen,
  Users,
  Bell,
  MessageSquare,
  LogOut,
  Menu,
  X,
} from "lucide-react";
import { Avatar } from "@/components/comments/Avatar";
import { useAuthStore } from "@/stores/auth";
import { cn } from "@/lib/utils";

const links = [
  { to: "/admin", label: "Tableau de bord", icon: LayoutDashboard, end: true },
  { to: "/admin/animes", label: "Animés", icon: Film },
  { to: "/admin/folders", label: "Dossiers", icon: FolderOpen },
  { to: "/admin/users", label: "Utilisateurs", icon: Users },
  { to: "/admin/broadcast", label: "Broadcast", icon: Bell },
  { to: "/admin/comments", label: "Commentaires", icon: MessageSquare },
];

function SidebarContent({ username, email, onLogout }: { username: string; email: string; onLogout: () => void }) {
  return (
    <>
      <div className="px-5 py-5">
        <Link to="/" className="font-display font-extrabold text-xl tracking-tight inline-flex items-center gap-2">
          Magi-<span className="text-primary">Stream</span>
          <span className="text-[10px] uppercase tracking-wider font-body font-bold bg-primary text-primary-foreground px-1.5 py-0.5 rounded">
            Admin
          </span>
        </Link>
      </div>
      <nav className="px-3 flex flex-col gap-1">
        {links.map((l) => {
          const Icon = l.icon;
          return (
            <NavLink
              key={l.to}
              to={l.to}
              end={l.end}
              className={({ isActive }) =>
                cn(
                  "flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-body font-semibold transition-colors relative",
                  isActive
                    ? "bg-primary/10 text-primary border-l-[3px] border-primary -ml-[3px] pl-[calc(0.75rem-3px)]"
                    : "text-muted-foreground hover:text-foreground hover:bg-surface",
                )
              }
            >
              <Icon className="w-4 h-4" />
              {l.label}
            </NavLink>
          );
        })}
      </nav>
      <div className="mt-auto px-3 pb-4">
        <div className="flex items-center gap-3 p-3 rounded-lg bg-surface border border-border">
          <Avatar name={username} size={32} />
          <div className="flex-1 min-w-0">
            <p className="text-sm font-body font-semibold truncate">{username}</p>
            <p className="text-xs text-muted-foreground font-body truncate">{email}</p>
          </div>
          <button onClick={onLogout} aria-label="Déconnexion" className="text-muted-foreground hover:text-foreground">
            <LogOut className="w-4 h-4" />
          </button>
        </div>
      </div>
    </>
  );
}

export function AdminLayout({ children }: { children?: ReactNode }) {
  const { user, isAuthenticated, isAdmin, logout } = useAuthStore();
  const [open, setOpen] = useState(false);
  const loc = useLocation();

  if (!isAuthenticated || !user) {
    return <Navigate to="/auth" state={{ from: loc.pathname }} replace />;
  }
  if (!isAdmin) {
    return <Navigate to="/" replace />;
  }

  const handleLogout = () => {
    logout();
  };

  return (
    <div className="min-h-screen bg-background flex">
      {/* Desktop sidebar */}
      <aside className="hidden md:flex flex-col w-60 shrink-0 bg-[hsl(var(--background))] border-r border-border min-h-screen sticky top-0">
        <SidebarContent username={user.username} email={user.email} onLogout={handleLogout} />
      </aside>

      {/* Mobile drawer */}
      <AnimatePresence>
        {open && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 z-50 md:hidden bg-background/80 backdrop-blur-md"
            onClick={() => setOpen(false)}
          >
            <motion.aside
              initial={{ x: -260 }}
              animate={{ x: 0 }}
              exit={{ x: -260 }}
              transition={{ type: "tween" }}
              onClick={(e) => e.stopPropagation()}
              className="w-60 h-full bg-background border-r border-border flex flex-col"
            >
              <SidebarContent username={user.username} email={user.email} onLogout={handleLogout} />
            </motion.aside>
          </motion.div>
        )}
      </AnimatePresence>

      <div className="flex-1 min-w-0">
        <header className="md:hidden sticky top-0 z-40 bg-background/85 backdrop-blur-xl border-b border-border h-14 flex items-center px-4 gap-3">
          <button onClick={() => setOpen(true)} aria-label="Ouvrir menu">
            {open ? <X className="w-5 h-5" /> : <Menu className="w-5 h-5" />}
          </button>
          <span className="font-display font-bold">Admin</span>
        </header>
        <motion.main
          key={loc.pathname}
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.25 }}
          className="p-4 md:p-8 max-w-[1400px]"
        >
          {children ?? <Outlet />}
        </motion.main>
      </div>
    </div>
  );
}
