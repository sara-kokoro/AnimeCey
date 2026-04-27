import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Send, Trash2, Loader2, Info, Sparkles, AlertTriangle, Wrench } from "lucide-react";
import { formatDistanceToNow } from "date-fns";
import { fr } from "date-fns/locale";
import { adminListBroadcasts, adminCreateBroadcast, adminDeleteBroadcast } from "@/api/admin";
import { toast } from "sonner";

const typeOptions = [
  { value: "info", label: "Info", icon: Info },
  { value: "new", label: "Nouveauté", icon: Sparkles },
  { value: "alert", label: "Alerte", icon: AlertTriangle },
  { value: "maintenance", label: "Maintenance", icon: Wrench },
];

export default function AdminBroadcast() {
  const qc = useQueryClient();
  const [title, setTitle] = useState("");
  const [content, setContent] = useState("");
  const [type, setType] = useState("info");
  const [target, setTarget] = useState("all");

  const { data: broadcasts = [], isLoading } = useQuery({
    queryKey: ["admin-broadcasts"],
    queryFn: adminListBroadcasts,
  });

  const sendMutation = useMutation({
    mutationFn: () => adminCreateBroadcast({ title, content, type, target }),
    onSuccess: () => {
      toast.success("Broadcast envoyé !");
      qc.invalidateQueries({ queryKey: ["admin-broadcasts"] });
      setTitle("");
      setContent("");
    },
    onError: () => toast.error("Erreur lors de l'envoi"),
  });

  const deleteMutation = useMutation({
    mutationFn: (id: number) => adminDeleteBroadcast(id),
    onSuccess: () => {
      toast.success("Broadcast supprimé");
      qc.invalidateQueries({ queryKey: ["admin-broadcasts"] });
    },
    onError: () => toast.error("Erreur"),
  });

  return (
    <div>
      <h1 className="font-display font-extrabold text-3xl mb-1">Broadcasts</h1>
      <p className="text-muted-foreground font-body mb-6">Envoie des notifications à tous les utilisateurs.</p>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <section className="bg-surface border border-border rounded-xl p-5">
          <h2 className="font-display font-bold text-lg mb-4">Nouveau broadcast</h2>
          <div className="space-y-4">
            <div>
              <label className="text-[11px] uppercase tracking-wider text-muted-foreground font-body font-semibold">Titre</label>
              <input
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                placeholder="Nouveaux épisodes disponibles..."
                className="mt-1 w-full bg-surface-2 border border-border rounded-lg px-3 py-2 text-sm font-body focus:outline-none focus:border-primary transition-colors"
              />
            </div>
            <div>
              <label className="text-[11px] uppercase tracking-wider text-muted-foreground font-body font-semibold">Message</label>
              <textarea
                value={content}
                onChange={(e) => setContent(e.target.value)}
                rows={4}
                placeholder="Le contenu du message..."
                className="mt-1 w-full bg-surface-2 border border-border rounded-lg px-3 py-2 text-sm font-body focus:outline-none focus:border-primary transition-colors resize-none"
              />
            </div>
            <div className="flex gap-3">
              <div className="flex-1">
                <label className="text-[11px] uppercase tracking-wider text-muted-foreground font-body font-semibold">Type</label>
                <select
                  value={type}
                  onChange={(e) => setType(e.target.value)}
                  className="mt-1 w-full bg-surface-2 border border-border rounded-lg px-3 py-2 text-sm font-body"
                >
                  {typeOptions.map((t) => (
                    <option key={t.value} value={t.value}>{t.label}</option>
                  ))}
                </select>
              </div>
              <div className="flex-1">
                <label className="text-[11px] uppercase tracking-wider text-muted-foreground font-body font-semibold">Cible</label>
                <select
                  value={target}
                  onChange={(e) => setTarget(e.target.value)}
                  className="mt-1 w-full bg-surface-2 border border-border rounded-lg px-3 py-2 text-sm font-body"
                >
                  <option value="all">Tout le monde</option>
                  <option value="users">Utilisateurs inscrits</option>
                </select>
              </div>
            </div>
            <button
              onClick={() => sendMutation.mutate()}
              disabled={!title.trim() || !content.trim() || sendMutation.isPending}
              className="w-full inline-flex items-center justify-center gap-2 px-4 py-2.5 rounded-lg bg-primary text-primary-foreground font-body font-semibold disabled:opacity-50"
            >
              {sendMutation.isPending ? <Loader2 className="w-4 h-4 animate-spin" /> : <Send className="w-4 h-4" />}
              {sendMutation.isPending ? "Envoi..." : "Envoyer"}
            </button>
          </div>
        </section>

        <section className="bg-surface border border-border rounded-xl p-5">
          <h2 className="font-display font-bold text-lg mb-4">Historique</h2>
          {isLoading ? (
            <div className="flex justify-center py-8"><Loader2 className="w-6 h-6 animate-spin text-primary" /></div>
          ) : (
            <div className="space-y-3 max-h-[500px] overflow-y-auto">
              {broadcasts.length === 0 && (
                <p className="text-sm text-muted-foreground font-body py-4 text-center">Aucun broadcast envoyé.</p>
              )}
              {(Array.isArray(broadcasts) ? broadcasts : broadcasts.items ?? []).map((b: Record<string, unknown>) => {
                const TypeIcon = typeOptions.find((t) => t.value === b.type)?.icon ?? Info;
                return (
                  <div key={String(b.id)} className="p-3 rounded-lg bg-surface-2 border border-border group">
                    <div className="flex items-start gap-3">
                      <TypeIcon className="w-4 h-4 mt-0.5 text-primary shrink-0" />
                      <div className="flex-1 min-w-0">
                        <p className="font-body font-semibold text-sm">{String(b.title)}</p>
                        <p className="text-xs text-muted-foreground font-body mt-0.5 line-clamp-2">{String(b.content)}</p>
                        <p className="text-[10px] text-muted-foreground/70 font-body mt-1">
                          {b.created_at ? formatDistanceToNow(new Date(String(b.created_at)), { addSuffix: true, locale: fr }) : ""}
                          {b.reads_count != null && ` · ${b.reads_count} lu${Number(b.reads_count) > 1 ? "s" : ""}`}
                        </p>
                      </div>
                      <button
                        onClick={() => deleteMutation.mutate(Number(b.id))}
                        className="opacity-0 group-hover:opacity-100 w-7 h-7 rounded-md hover:bg-destructive/10 text-destructive flex items-center justify-center transition-opacity"
                      >
                        <Trash2 className="w-3.5 h-3.5" />
                      </button>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </section>
      </div>
    </div>
  );
}
