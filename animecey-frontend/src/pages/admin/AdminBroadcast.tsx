import { useState } from "react";
import { Info, Sparkles, AlertTriangle, Wrench, ImagePlus, X } from "lucide-react";
import { ToggleGroup2 } from "@/components/ui/ToggleGroup2";
import { mockBroadcasts } from "@/data/mock";
import { formatDistanceToNow } from "date-fns";
import { fr } from "date-fns/locale";
import { toast } from "sonner";
import { cn } from "@/lib/utils";

const types = [
  { value: "info", label: "Info", icon: Info, color: "text-info" },
  { value: "new", label: "Nouveauté", icon: Sparkles, color: "text-primary" },
  { value: "alert", label: "Alerte", icon: AlertTriangle, color: "text-destructive" },
  { value: "maintenance", label: "Maintenance", icon: Wrench, color: "text-warning" },
] as const;

export default function AdminBroadcast() {
  const [type, setType] = useState<(typeof types)[number]["value"]>("new");
  const [target, setTarget] = useState<"all" | "users">("all");
  const [title, setTitle] = useState("");
  const [content, setContent] = useState("");
  const [imgUrl, setImgUrl] = useState("");
  const [caption, setCaption] = useState("");

  const TypeIcon = types.find((t) => t.value === type)!.icon;
  const typeColor = types.find((t) => t.value === type)!.color;

  const send = () => {
    if (!title.trim() || !content.trim()) {
      toast.error("Renseigne au moins un titre et un contenu");
      return;
    }
    toast.success(`Broadcast envoyé à ${target === "all" ? "tous les visiteurs" : "tous les utilisateurs"}`);
    setTitle("");
    setContent("");
    setImgUrl("");
    setCaption("");
  };

  return (
    <div>
      <h1 className="font-display font-extrabold text-3xl mb-1">Broadcast</h1>
      <p className="text-muted-foreground font-body mb-6">Envoie un message à tous les visiteurs ou utilisateurs.</p>

      <div className="grid grid-cols-1 lg:grid-cols-[1fr_360px] gap-6">
        {/* Form */}
        <section className="bg-surface border border-border rounded-xl p-5 space-y-5">
          <div>
            <label className="text-xs uppercase tracking-wider font-body font-semibold text-muted-foreground">
              Titre
            </label>
            <input
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              className="mt-1 w-full bg-surface-2 border border-border rounded-lg px-3 py-2 text-sm font-body focus:outline-none focus:border-primary transition-colors"
            />
          </div>

          <div>
            <label className="text-xs uppercase tracking-wider font-body font-semibold text-muted-foreground block mb-2">
              Type
            </label>
            <div className="flex flex-wrap gap-2">
              {types.map((t) => {
                const Icon = t.icon;
                const active = type === t.value;
                return (
                  <button
                    key={t.value}
                    onClick={() => setType(t.value)}
                    className={cn(
                      "inline-flex items-center gap-2 px-3 py-1.5 rounded-lg border text-sm font-body font-semibold transition-all",
                      active
                        ? "bg-primary text-primary-foreground border-primary"
                        : "bg-surface-2 border-border text-muted-foreground hover:border-primary/40",
                    )}
                  >
                    <Icon className="w-4 h-4" />
                    {t.label}
                  </button>
                );
              })}
            </div>
          </div>

          <div>
            <label className="text-xs uppercase tracking-wider font-body font-semibold text-muted-foreground block mb-2">
              Cible
            </label>
            <ToggleGroup2
              value={target}
              onChange={(v) => setTarget(v as "all" | "users")}
              options={[
                { value: "all", label: "Tous les visiteurs" },
                { value: "users", label: "Utilisateurs connectés" },
              ]}
            />
          </div>

          <div>
            <label className="text-xs uppercase tracking-wider font-body font-semibold text-muted-foreground">
              Contenu
            </label>
            <textarea
              value={content}
              onChange={(e) => setContent(e.target.value)}
              rows={6}
              className="mt-1 w-full bg-surface-2 border border-border rounded-lg px-3 py-2 text-sm font-body resize-none focus:outline-none focus:border-primary transition-colors"
            />
          </div>

          <div>
            <label className="text-xs uppercase tracking-wider font-body font-semibold text-muted-foreground">
              Image (URL)
            </label>
            <div className="mt-1 flex gap-2">
              <input
                value={imgUrl}
                onChange={(e) => setImgUrl(e.target.value)}
                placeholder="https://..."
                className="flex-1 bg-surface-2 border border-border rounded-lg px-3 py-2 text-sm font-body focus:outline-none focus:border-primary transition-colors"
              />
              {imgUrl && (
                <button onClick={() => setImgUrl("")} aria-label="Retirer" className="px-3 rounded-lg bg-surface-2 border border-border">
                  <X className="w-4 h-4" />
                </button>
              )}
              {!imgUrl && (
                <button className="inline-flex items-center gap-2 px-3 rounded-lg bg-surface-2 border border-border text-sm font-body font-semibold">
                  <ImagePlus className="w-4 h-4" />
                </button>
              )}
            </div>
            {imgUrl && (
              <input
                value={caption}
                onChange={(e) => setCaption(e.target.value)}
                placeholder="Légende de l'image..."
                className="mt-2 w-full bg-surface-2 border border-border rounded-lg px-3 py-2 text-sm font-body italic focus:outline-none focus:border-primary transition-colors"
              />
            )}
          </div>

          <button
            onClick={send}
            className="w-full md:w-auto px-6 py-3 rounded-lg bg-primary text-primary-foreground font-body font-semibold"
          >
            Envoyer à {target === "all" ? "tous" : "aux utilisateurs"}
          </button>
        </section>

        {/* Preview */}
        <aside>
          <p className="text-xs uppercase tracking-wider font-body font-semibold text-muted-foreground mb-2">
            Aperçu
          </p>
          <div className="bg-surface border border-border rounded-xl p-4">
            <div className="flex gap-3">
              <TypeIcon className={cn("w-4 h-4 mt-0.5 shrink-0", typeColor)} />
              <div className="flex-1 min-w-0">
                <p className="font-body font-semibold text-sm">{title || "Titre du broadcast"}</p>
                <p className="text-xs text-muted-foreground font-body line-clamp-3 mt-0.5">
                  {content || "Contenu du message..."}
                </p>
                {imgUrl && (
                  <div className="mt-2 rounded-lg overflow-hidden">
                    <img src={imgUrl} alt="" className="w-full h-auto" />
                  </div>
                )}
                {caption && <p className="italic text-xs text-muted-foreground font-body mt-1">{caption}</p>}
                <p className="text-[11px] text-muted-foreground/70 font-body mt-1.5">à l'instant</p>
              </div>
            </div>
          </div>
        </aside>
      </div>

      <section className="mt-10">
        <h2 className="font-display font-bold text-lg mb-3">Historique des broadcasts</h2>
        <div className="bg-surface border border-border rounded-xl overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-surface-2 border-b border-border">
              <tr className="text-left font-body font-semibold text-muted-foreground">
                <th className="px-4 py-3">Titre</th>
                <th className="px-4 py-3 hidden md:table-cell">Type</th>
                <th className="px-4 py-3 hidden md:table-cell">Cible</th>
                <th className="px-4 py-3 hidden md:table-cell">Lectures</th>
                <th className="px-4 py-3">Date</th>
              </tr>
            </thead>
            <tbody>
              {mockBroadcasts.map((b) => (
                <tr key={b.id} className="border-b border-border-subtle last:border-b-0">
                  <td className="px-4 py-3 font-body font-semibold">{b.title}</td>
                  <td className="px-4 py-3 hidden md:table-cell text-muted-foreground capitalize">{b.type}</td>
                  <td className="px-4 py-3 hidden md:table-cell text-muted-foreground">{b.target}</td>
                  <td className="px-4 py-3 hidden md:table-cell text-muted-foreground">{b.reads_count}</td>
                  <td className="px-4 py-3 text-muted-foreground text-xs">
                    {formatDistanceToNow(new Date(b.created_at), { addSuffix: true, locale: fr })}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}