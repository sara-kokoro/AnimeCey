import { useState } from "react";
import { Search, Trash2 } from "lucide-react";
import { Avatar } from "@/components/comments/Avatar";
import { animes, getComments } from "@/data/mock";
import { formatDistanceToNow } from "date-fns";
import { fr } from "date-fns/locale";

export default function AdminComments() {
  const [query, setQuery] = useState("");
  // build a flat list of comments across animes for mock
  const all = animes.slice(0, 4).flatMap((a) =>
    getComments(a.id * 1000 + 101).map((c) => ({ ...c, anime: a.title })),
  );
  const list = all.filter((c) => c.content.toLowerCase().includes(query.toLowerCase()));

  return (
    <div>
      <h1 className="font-display font-extrabold text-3xl mb-1">Commentaires</h1>
      <p className="text-muted-foreground font-body mb-6">Modération des messages publiés sur les épisodes.</p>

      <div className="relative mb-4 max-w-md">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
        <input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Rechercher dans les commentaires..."
          className="w-full bg-surface border border-border rounded-lg pl-9 pr-3 py-2 text-sm font-body focus:outline-none focus:border-primary transition-colors"
        />
      </div>

      <div className="space-y-2">
        {list.map((c) => (
          <div key={c.id} className="bg-surface border border-border rounded-xl p-4 flex gap-3">
            <Avatar name={c.user.username} />
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2 flex-wrap">
                <span className="font-body font-semibold text-sm">{c.user.username}</span>
                <span className="text-xs text-muted-foreground font-body">sur</span>
                <span className="text-xs font-body font-semibold text-primary">{c.anime}</span>
                <span className="text-xs text-muted-foreground font-body">·</span>
                <span className="text-xs text-muted-foreground font-body">
                  {formatDistanceToNow(new Date(c.created_at), { addSuffix: true, locale: fr })}
                </span>
              </div>
              <p className="text-sm font-body text-foreground mt-1">{c.content}</p>
              <p className="text-xs text-muted-foreground font-body mt-1.5">{c.likes_count} j'aime</p>
            </div>
            <button aria-label="Supprimer" className="self-start w-8 h-8 rounded-md hover:bg-destructive/10 text-destructive flex items-center justify-center">
              <Trash2 className="w-4 h-4" />
            </button>
          </div>
        ))}
        {list.length === 0 && (
          <p className="text-center text-sm text-muted-foreground font-body py-8">Aucun commentaire trouvé</p>
        )}
      </div>
    </div>
  );
}