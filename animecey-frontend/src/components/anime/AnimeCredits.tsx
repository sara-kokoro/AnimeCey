import { useQuery } from "@tanstack/react-query";
import { User } from "lucide-react";
import { fetchCredits, type CreditPerson } from "@/api/animes";

function Avatar({ src, alt, className }: { src: string | null; alt: string; className: string }) {
  return (
    <div className={`${className} shrink-0 overflow-hidden rounded-full bg-surface-2 ring-1 ring-foreground/10 flex items-center justify-center`}>
      {src ? (
        <img src={src} alt={alt} loading="lazy" className="w-full h-full object-cover" />
      ) : (
        <User className="w-1/2 h-1/2 text-muted-foreground" />
      )}
    </div>
  );
}

function PersonCard({ person }: { person: CreditPerson }) {
  return (
    <li className="flex items-center gap-3 rounded-xl bg-surface border border-border-subtle p-2.5 min-w-0">
      <Avatar src={person.image} alt={person.name} className="w-12 h-12" />
      <div className="min-w-0 flex-1">
        <p className="font-semibold text-sm leading-tight truncate">{person.name}</p>
        {person.role && <p className="text-[11px] text-muted-foreground truncate">{person.role}</p>}
        {person.sub_name && (
          <p className="text-[11px] text-foreground/70 truncate">Voix : {person.sub_name}</p>
        )}
      </div>
      {person.sub_name && <Avatar src={person.sub_image} alt={person.sub_name} className="w-10 h-10" />}
    </li>
  );
}

/**
 * Personnages / équipe sous les infos de la fiche.
 * Animés : données AniList. Films et séries : distribution et équipe TMDB.
 */
export function AnimeCredits({ animeId }: { animeId: number }) {
  const { data, isLoading } = useQuery({
    queryKey: ["credits", animeId],
    queryFn: () => fetchCredits(animeId),
    staleTime: 10 * 60_000,
    retry: 1,
  });

  if (isLoading || !data || data.groups.length === 0) return null;

  return (
    <div className="space-y-6">
      {data.groups.map((group) => (
        <section key={group.title}>
          <div className="flex items-baseline justify-between mb-2">
            <h2 className="font-display font-bold text-lg">{group.title}</h2>
            <span className="text-[10px] uppercase tracking-wider text-muted-foreground">
              {data.source === "anilist" ? "Source : AniList" : "Source : TMDB"}
            </span>
          </div>
          <ul className="grid grid-cols-1 sm:grid-cols-2 gap-2">
            {group.people.map((p, i) => (
              <PersonCard key={`${p.name}-${p.role}-${i}`} person={p} />
            ))}
          </ul>
        </section>
      ))}
    </div>
  );
}
