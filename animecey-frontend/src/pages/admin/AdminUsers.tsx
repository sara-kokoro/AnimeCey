import { useState } from "react";
import { Search, Shield, Trash2 } from "lucide-react";
import { Avatar } from "@/components/comments/Avatar";
import { mockUsers } from "@/data/mock";
import { format } from "date-fns";
import { fr } from "date-fns/locale";
import { cn } from "@/lib/utils";

export default function AdminUsers() {
  const [query, setQuery] = useState("");
  const [role, setRole] = useState<"all" | "user" | "admin">("all");

  const list = mockUsers.filter((u) => {
    if (role !== "all" && u.role !== role) return false;
    if (query && !u.username.toLowerCase().includes(query.toLowerCase()) && !u.email.includes(query))
      return false;
    return true;
  });

  return (
    <div>
      <h1 className="font-display font-extrabold text-3xl mb-1">Utilisateurs</h1>
      <p className="text-muted-foreground font-body mb-6">{mockUsers.length} comptes au total.</p>

      <div className="flex flex-col md:flex-row gap-3 mb-4">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Rechercher par pseudo ou email..."
            className="w-full bg-surface border border-border rounded-lg pl-9 pr-3 py-2 text-sm font-body focus:outline-none focus:border-primary transition-colors"
          />
        </div>
        <div className="flex gap-1 bg-surface border border-border rounded-lg p-1">
          {(["all", "user", "admin"] as const).map((r) => (
            <button
              key={r}
              onClick={() => setRole(r)}
              className={cn(
                "px-3 py-1 rounded-md text-xs font-body font-semibold transition-colors capitalize",
                role === r ? "bg-primary text-primary-foreground" : "text-muted-foreground hover:text-foreground",
              )}
            >
              {r === "all" ? "Tous" : r}
            </button>
          ))}
        </div>
      </div>

      <div className="bg-surface border border-border rounded-xl overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-surface-2 border-b border-border">
            <tr className="text-left font-body font-semibold text-muted-foreground">
              <th className="px-4 py-3">Utilisateur</th>
              <th className="px-4 py-3 hidden md:table-cell">Email</th>
              <th className="px-4 py-3">Rôle</th>
              <th className="px-4 py-3 hidden md:table-cell">Inscription</th>
              <th className="px-4 py-3 text-right">Actions</th>
            </tr>
          </thead>
          <tbody>
            {list.map((u) => (
              <tr key={u.id} className="border-b border-border-subtle last:border-b-0 hover:bg-surface-2 transition-colors">
                <td className="px-4 py-3">
                  <div className="flex items-center gap-3">
                    <Avatar name={u.username} size={32} />
                    <span className="font-body font-semibold">{u.username}</span>
                  </div>
                </td>
                <td className="px-4 py-3 hidden md:table-cell text-muted-foreground">{u.email}</td>
                <td className="px-4 py-3">
                  <span
                    className={cn(
                      "text-[10px] uppercase tracking-wider font-body font-bold px-1.5 py-0.5 rounded",
                      u.role === "admin"
                        ? "bg-primary/10 text-primary border border-primary/30"
                        : "bg-surface text-muted-foreground border border-border",
                    )}
                  >
                    {u.role}
                  </span>
                </td>
                <td className="px-4 py-3 hidden md:table-cell text-muted-foreground text-xs">
                  {format(new Date(u.created_at), "dd MMM yyyy", { locale: fr })}
                </td>
                <td className="px-4 py-3 text-right">
                  <div className="inline-flex gap-1">
                    <button aria-label="Toggle admin" className="w-8 h-8 rounded-md hover:bg-surface flex items-center justify-center text-muted-foreground hover:text-primary transition-colors">
                      <Shield className="w-4 h-4" />
                    </button>
                    <button aria-label="Supprimer" className="w-8 h-8 rounded-md hover:bg-destructive/10 flex items-center justify-center text-destructive transition-colors">
                      <Trash2 className="w-4 h-4" />
                    </button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}