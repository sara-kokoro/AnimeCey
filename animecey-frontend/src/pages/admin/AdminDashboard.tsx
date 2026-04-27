import { Film, Play, Users, MessageSquare, Plus } from "lucide-react";
import { Link } from "react-router-dom";
import { formatDistanceToNow } from "date-fns";
import { fr } from "date-fns/locale";
import { animes, mockUsers, mockRecentUploads } from "@/data/mock";

const stats = [
  { icon: Film, label: "Animés", value: animes.length },
  { icon: Play, label: "Épisodes", value: animes.reduce((s, a) => s + a.episodes_count, 0) },
  { icon: Users, label: "Utilisateurs", value: mockUsers.length },
  { icon: MessageSquare, label: "Commentaires", value: 1248 },
];

const shortcuts = [
  { to: "/admin/animes", label: "Ajouter un anime" },
  { to: "/admin/folders", label: "Créer un dossier" },
  { to: "/admin/broadcast", label: "Envoyer un broadcast" },
];

export default function AdminDashboard() {
  return (
    <div>
      <h1 className="font-display font-extrabold text-3xl mb-1">Tableau de bord</h1>
      <p className="text-muted-foreground font-body mb-8">Vue d'ensemble de la plateforme.</p>

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-10">
        {stats.map((s) => {
          const Icon = s.icon;
          return (
            <div key={s.label} className="bg-surface border border-border rounded-xl p-5">
              <Icon className="w-5 h-5 text-primary mb-3" />
              <p className="font-display font-extrabold text-3xl md:text-4xl">{s.value}</p>
              <p className="text-xs uppercase tracking-wider font-body font-semibold text-muted-foreground mt-1">
                {s.label}
              </p>
            </div>
          );
        })}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <section className="lg:col-span-2 bg-surface border border-border rounded-xl p-5">
          <h2 className="font-display font-bold text-lg mb-4">Derniers uploads</h2>
          <div className="space-y-3">
            {mockRecentUploads.map((u) => (
              <div key={u.id} className="flex items-center gap-3 p-2 rounded-lg hover:bg-surface-2 transition-colors">
                <img src={u.thumbnail} alt="" className="w-20 aspect-video object-cover rounded" />
                <div className="flex-1 min-w-0">
                  <p className="font-body font-semibold text-sm truncate">{u.anime_title}</p>
                  <p className="text-xs text-muted-foreground font-body">{u.episode_label}</p>
                </div>
                <span className="text-[10px] uppercase font-body font-bold text-primary bg-primary/10 px-1.5 py-0.5 rounded border border-primary/30">
                  {u.language}
                </span>
                <span className="text-xs text-muted-foreground font-body whitespace-nowrap">
                  {formatDistanceToNow(new Date(u.uploaded_at), { addSuffix: true, locale: fr })}
                </span>
              </div>
            ))}
          </div>
        </section>

        <section className="bg-surface border border-border rounded-xl p-5">
          <h2 className="font-display font-bold text-lg mb-4">Raccourcis</h2>
          <div className="flex flex-col gap-2">
            {shortcuts.map((s) => (
              <Link
                key={s.to}
                to={s.to}
                className="inline-flex items-center gap-2 px-3 py-2.5 rounded-lg bg-surface-2 border border-border text-sm font-body font-semibold hover:border-primary/40 transition-colors"
              >
                <Plus className="w-4 h-4 text-primary" />
                {s.label}
              </Link>
            ))}
          </div>
        </section>
      </div>
    </div>
  );
}