import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Search, Shield, ShieldCheck, Trash2, Loader2 } from "lucide-react";
import { formatDistanceToNow } from "date-fns";
import { fr } from "date-fns/locale";
import { adminListUsers, adminSetRole, adminDeleteUser } from "@/api/admin";
import { toast } from "sonner";

export default function AdminUsers() {
  const qc = useQueryClient();
  const [search, setSearch] = useState("");
  const [roleFilter, setRoleFilter] = useState("");
  const [page, setPage] = useState(1);

  const { data, isLoading } = useQuery({
    queryKey: ["admin-users", page, search, roleFilter],
    queryFn: () => adminListUsers(page, 24, search || undefined, roleFilter || undefined),
  });

  const roleMutation = useMutation({
    mutationFn: ({ userId, role }: { userId: number; role: string }) => adminSetRole(userId, role),
    onSuccess: () => {
      toast.success("Rôle mis à jour");
      qc.invalidateQueries({ queryKey: ["admin-users"] });
    },
    onError: () => toast.error("Erreur"),
  });

  const deleteMutation = useMutation({
    mutationFn: (id: number) => adminDeleteUser(id),
    onSuccess: () => {
      toast.success("Utilisateur supprimé");
      qc.invalidateQueries({ queryKey: ["admin-users"] });
      qc.invalidateQueries({ queryKey: ["admin-stats"] });
    },
    onError: () => toast.error("Erreur"),
  });

  const users = data?.items ?? [];

  return (
    <div>
      <h1 className="font-display font-extrabold text-3xl mb-1">Utilisateurs</h1>
      <p className="text-muted-foreground font-body mb-6">
        {data?.total ?? 0} utilisateurs inscrits.
      </p>

      <div className="flex flex-col md:flex-row gap-3 mb-5">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
          <input
            value={search}
            onChange={(e) => { setSearch(e.target.value); setPage(1); }}
            placeholder="Rechercher un utilisateur..."
            className="w-full bg-surface border border-border rounded-lg pl-9 pr-3 py-2 text-sm font-body focus:outline-none focus:border-primary transition-colors"
          />
        </div>
        <select
          value={roleFilter}
          onChange={(e) => { setRoleFilter(e.target.value); setPage(1); }}
          className="bg-surface border border-border rounded-lg px-3 py-2 text-sm font-body"
        >
          <option value="">Tous les rôles</option>
          <option value="admin">Admin</option>
          <option value="user">User</option>
        </select>
      </div>

      {isLoading ? (
        <div className="flex justify-center py-12"><Loader2 className="w-6 h-6 animate-spin text-primary" /></div>
      ) : (
        <div className="bg-surface border border-border rounded-xl overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-surface-2 border-b border-border">
              <tr className="text-left font-body font-semibold text-muted-foreground">
                <th className="px-4 py-3">Nom</th>
                <th className="px-4 py-3 hidden md:table-cell">Email</th>
                <th className="px-4 py-3">Rôle</th>
                <th className="px-4 py-3 hidden md:table-cell">Inscrit</th>
                <th className="px-4 py-3 text-right">Actions</th>
              </tr>
            </thead>
            <tbody>
              {users.length === 0 && (
                <tr>
                  <td colSpan={5} className="px-4 py-8 text-center text-muted-foreground font-body">Aucun utilisateur.</td>
                </tr>
              )}
              {users.map((u: Record<string, unknown>) => (
                <tr key={String(u.id)} className="border-b border-border-subtle last:border-b-0 hover:bg-surface-2 transition-colors">
                  <td className="px-4 py-3 font-body font-semibold">{String(u.username)}</td>
                  <td className="px-4 py-3 hidden md:table-cell text-muted-foreground">{String(u.email)}</td>
                  <td className="px-4 py-3">
                    <span className={`inline-flex items-center gap-1 text-xs font-body font-bold px-2 py-0.5 rounded ${u.role === "admin" ? "bg-primary/10 text-primary" : "bg-surface-2 text-muted-foreground"}`}>
                      {u.role === "admin" ? <ShieldCheck className="w-3 h-3" /> : <Shield className="w-3 h-3" />}
                      {String(u.role).toUpperCase()}
                    </span>
                  </td>
                  <td className="px-4 py-3 hidden md:table-cell text-xs text-muted-foreground">
                    {u.created_at ? formatDistanceToNow(new Date(String(u.created_at)), { addSuffix: true, locale: fr }) : "?"}
                  </td>
                  <td className="px-4 py-3 text-right">
                    <div className="inline-flex gap-1">
                      <button
                        onClick={() => roleMutation.mutate({ userId: Number(u.id), role: u.role === "admin" ? "user" : "admin" })}
                        title={u.role === "admin" ? "Retirer admin" : "Rendre admin"}
                        className="w-8 h-8 rounded-md hover:bg-primary/10 flex items-center justify-center text-primary"
                      >
                        {u.role === "admin" ? <Shield className="w-4 h-4" /> : <ShieldCheck className="w-4 h-4" />}
                      </button>
                      <button
                        onClick={() => { if (confirm("Supprimer cet utilisateur ?")) deleteMutation.mutate(Number(u.id)); }}
                        className="w-8 h-8 rounded-md hover:bg-destructive/10 flex items-center justify-center text-destructive"
                      >
                        <Trash2 className="w-4 h-4" />
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>

          {(data?.pages ?? 1) > 1 && (
            <div className="flex justify-center gap-2 p-4 border-t border-border">
              <button disabled={page <= 1} onClick={() => setPage((p) => p - 1)} className="px-3 py-1.5 rounded-lg text-xs font-body font-semibold bg-surface-2 border border-border disabled:opacity-40">Précédent</button>
              <span className="px-3 py-1.5 text-xs font-body text-muted-foreground">Page {page} / {data?.pages ?? 1}</span>
              <button disabled={page >= (data?.pages ?? 1)} onClick={() => setPage((p) => p + 1)} className="px-3 py-1.5 rounded-lg text-xs font-body font-semibold bg-surface-2 border border-border disabled:opacity-40">Suivant</button>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
