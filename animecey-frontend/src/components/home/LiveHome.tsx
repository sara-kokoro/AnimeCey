import { Clapperboard } from "lucide-react";
import { Link } from "react-router-dom";
import { Section } from "@/components/home/Section";
import { LiveHero } from "@/components/home/LiveHero";
import { RankedRow } from "@/components/home/RankedRow";
import { HorizontalScroll } from "@/components/ui/HorizontalScroll";
import { AnimeCard } from "@/components/anime/AnimeCard";
import type { LiveHomeData } from "@/api/animes";
import type { Anime } from "@/types";

function Row({ title, items, href }: { title: string; items?: Anime[]; href?: string }) {
  if (!items || items.length === 0) return null;
  return (
    <Section title={title} href={href}>
      <HorizontalScroll>
        {items.slice(0, 12).map((a, i) => (
          <AnimeCard key={a.id} anime={a} index={i} />
        ))}
      </HorizontalScroll>
    </Section>
  );
}

/** Zone « Films & Séries » de l'accueil : bandeau du jour, top 10, nouveautés, mieux notés, genres... */
export function LiveHome({ data }: { data: LiveHomeData }) {
  const all = "/catalogue?category=live";
  return (
    <div className="mt-16 md:mt-20">
      <div className="flex items-end justify-between gap-4 mb-5">
        <div>
          <h2 className="font-display font-extrabold text-2xl md:text-4xl text-foreground inline-flex items-center gap-3">
            <Clapperboard className="w-7 h-7 md:w-9 md:h-9 text-primary" />
            Films &amp; Séries
          </h2>
          <p className="mt-2 text-sm md:text-base text-muted-foreground font-body max-w-xl">
            Les films et séries du moment, avec de vrais acteurs, en VF et VOSTFR.
          </p>
        </div>
        <Link
          to={all}
          className="hidden sm:inline-flex text-sm font-body font-semibold text-primary hover:text-primary-dim transition-colors"
        >
          Tout voir
        </Link>
      </div>

      <LiveHero items={data.featured} />

      {data.top_week.length > 0 && (
        <Section title="Top 10 de la semaine · Films & Séries">
          <HorizontalScroll>
            <RankedRow data={data.top_week} isLoading={false} />
          </HorizontalScroll>
        </Section>
      )}

      <Row title="Nouveautés du moment" items={data.new_releases} href={all} />
      <Row title="Les mieux notés" items={data.top_rated} href={all} />
      <Row title="Films à voir" items={data.films} href="/films?category=live" />
      <Row title="Séries à regarder" items={data.series} href="/series?category=live" />
      {data.genres.map((g) => (
        <Row key={g.genre} title={g.genre} items={g.items} href={`/genre/${encodeURIComponent(g.genre)}?category=live`} />
      ))}
      <Row title="Derniers ajouts" items={data.latest} href={all} />
    </div>
  );
}
