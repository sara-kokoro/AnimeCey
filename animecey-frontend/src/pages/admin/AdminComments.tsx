import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Search, Trash2, Loader2, MessageSquare } from "lucide-react";
import { formatDistanceToNow } from "date-fns";
import { fr } from "date-fns/locale";
import { adminListComments, adminDeleteComment } from "@/api/admin";
import { getApiError } from "@/api/axios";
import { toast } from "sonner";

export default function AdminComments() {
  const qc = useQueryClient();
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(1);

  const { data, isLoading } = useQuery({
    queryKey: ["admin-comments", page, search],
    queryFn: () => adminListComments(page, 20, search || undefined),
  });

  const deleteMutation = useMutation({
    mutationFn: (id: number) => adminDeleteComment(id),
    onSuccess: () => {
      toast.success("Commentaire supprimé");
      qc.invalidateQueries({ queryKey: ["admin-comments"] });
      qc.invalidateQueries({ queryKey: ["admin-stats"] });
    },
    onError: (err: unknown) => toast.error(getApiError(err, "Erreur")),
  });

  const comments = data?.items ?? [];

  return (
    <div>
      <h1 className="font-display font-extrabold text-3xl mb-1">Commentaires</h1>
      <p className="text-muted-foreground font-body mb-6">
        {data?.total ?? 0} commentaires au total.
      </p>

      <div className="relative max-w-md mb-5">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
        <input
          value={search}
          onChange={(e) => { setSearch(e.target.value); setPage(1); }}
          placeholder="Rechercher dans les commentaires..."
          className="w-full bg-surface border border-border rounded-lg pl-9 pr-3 py-2 text-sm font-body focus:outline-none focus:border-primary transition-colors"
        />
      </div>

      {isLoading ? (
        <div className="flex justify-center py-12"><Loader2 className="w-6 h-6 animate-spin text-primary" /></div>
      ) : (
        <div className="space-y-2">
          {comments.length === 0 && (
            <div className="bg-surface border border-border rounded-xl p-8 text-center">
              <MessageSquare className="w-8 h-8 mx-auto text-muted-foreground mb-2" />
              <p className="text-sm text-muted-foreground font-body">Aucun commentaire.</p>
            </div>
          )}
          {comments.map((c: Record<string, unknown>) => {
            const user = c.user as Record<string, unknown> | undefined;
            return (
              <div key={String(c.id)} className="flex gap-3 p-3 bg-surface border border-border rounded-lg group hover:border-border-subtle transition-colors">
                <div className="flex-1 min-w-0">
                  <div className="flex items-baseline gap-2 flex-wrap">
                    <span className="font-body font-semibold text-sm">
                      {user?.username ? String(user.username) : "Utilisateur"}
                    </span>
                    {c.anime_title && (
                      <span className="text-xs text-muted-foreground font-body">
                        sur {String(c.anime_title)}
                      </span>
                    )}
                    {c.episode_number != null && (
                      <span className="text-xs text-muted-foreground font-body">
                        — Épisode {String(c.episode_number)}
                      </span>
                    )}
                    <span className="text-xs text-muted-foreground/70 font-body">
                      {c.created_at ? formatDistanceToNow(new Date(String(c.created_at)), { addSuffix: true, locale: fr }) : ""}
                    </span>
                  </div>
                  <p className="text-sm text-foreground/90 font-body mt-1">{String(c.content)}</p>
                </div>
                <button
                  onClick={() => { if (confirm("Supprimer ce commentaire ?")) deleteMutation.mutate(Number(c.id)); }}
                  className="opacity-0 group-hover:opacity-100 w-8 h-8 rounded-md hover:bg-destructive/10 flex items-center justify-center text-destructive transition-opacity shrink-0"
                >
                  <Trash2 className="w-4 h-4" />
                </button>
              </div>
            );
          })}

          {(data?.pages ?? 1) > 1 && (
            <div className="flex justify-center gap-2 pt-4">
              <button disabled={page <= 1} onClick={() => setPage((p) => p - 1)} className="px-3 py-1.5 rounded-lg text-xs font-body font-semibold bg-surface border border-border disabled:opacity-40">Précédent</button>
              <span className="px-3 py-1.5 text-xs font-body text-muted-foreground">Page {page} / {data?.pages ?? 1}</span>
              <button disabled={page >= (data?.pages ?? 1)} onClick={() => setPage((p) => p + 1)} className="px-3 py-1.5 rounded-lg text-xs font-body font-semibold bg-surface border border-border disabled:opacity-40">Suivant</button>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
