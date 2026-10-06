import { useQuery } from "@tanstack/react-query";
import { Navbar } from "@/components/layout/Navbar";
import { Footer } from "@/components/layout/Footer";
import { HeroCarousel } from "@/components/home/HeroCarousel";
import { Section } from "@/components/home/Section";
import { HorizontalScroll } from "@/components/ui/HorizontalScroll";
import { RankedRow } from "@/components/home/RankedRow";
import { AnimeCard } from "@/components/anime/AnimeCard";
import { SkeletonCard } from "@/components/ui/SkeletonCard";
import { LiveHome } from "@/components/home/LiveHome";
import { fetchLiveHome, fetchTopWeek, fetchTopRated, fetchLatest, fetchTrending } from "@/api/animes";
import { motion } from "framer-motion";

function CardList({ data, isLoading }: { data?: unknown[]; isLoading: boolean }) {
  if (isLoading) return <>{Array.from({ length: 6 }).map((_, i) => <SkeletonCard key={i} />)}</>;
  if (!data || data.length === 0) return <p className="text-muted-foreground text-sm">Aucun résultat</p>;
  return <>{(data as Record<string, unknown>[]).slice(0, 10).map((a, i) => <AnimeCard key={String(a.id)} anime={a as never} index={i} />)}</>;
}

const SEASON_NAMES = ["Hiver", "Hiver", "Hiver", "Printemps", "Printemps", "Printemps", "Été", "Été", "Été", "Automne", "Automne", "Automne"];

function seasonLabel(): string {
  const d = new Date();
  return `${SEASON_NAMES[d.getMonth()]} ${d.getFullYear()}`;
}

export default function Home() {
  const topWeek = useQuery({ queryKey: ["top-week"], queryFn: fetchTopWeek });
  const topRated = useQuery({ queryKey: ["top-rated"], queryFn: fetchTopRated });
  const latest = useQuery({ queryKey: ["latest"], queryFn: fetchLatest });
  const trending = useQuery({ queryKey: ["trending"], queryFn: fetchTrending });
  // Films & séries (live-action) : une requête pour toute la zone ; rien ne s'affiche s'il n'y en a pas encore
  const live = useQuery({ queryKey: ["live-home"], queryFn: fetchLiveHome, staleTime: 60_000 });
  const hasLive = !!live.data && (live.data.featured.length > 0 || live.data.latest.length > 0);

  const jump = (id: string) => document.getElementById(id)?.scrollIntoView({ behavior: "smooth", block: "start" });

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4 }}
      className="min-h-screen bg-background"
    >
      <Navbar />
      <HeroCarousel />

      <main className="mx-auto max-w-7xl px-4 md:px-6">
        {hasLive && (
          <div className="mt-6 flex gap-2">
            <button
              onClick={() => jump("animes")}
              className="px-4 py-2 rounded-full bg-primary text-primary-foreground text-sm font-body font-semibold"
            >
              Animés
            </button>
            <button
              onClick={() => jump("films-series")}
              className="px-4 py-2 rounded-full bg-surface border border-border-subtle text-foreground text-sm font-body font-semibold hover:bg-surface-2 transition-colors"
            >
              Films &amp; Séries
            </button>
          </div>
        )}
        <div id="animes" className="scroll-mt-24" />
        {(topWeek.isLoading || (topWeek.data && topWeek.data.length > 0)) && (
          <Section title="Top 10 de la semaine">
            <HorizontalScroll>
              <RankedRow data={topWeek.data as never} isLoading={topWeek.isLoading} />
            </HorizontalScroll>
          </Section>
        )}

        <Section title="Les mieux notés">
          <HorizontalScroll>
            <CardList data={topRated.data} isLoading={topRated.isLoading} />
          </HorizontalScroll>
        </Section>

        <Section title="Derniers ajouts">
          <HorizontalScroll>
            <CardList data={latest.data} isLoading={latest.isLoading} />
          </HorizontalScroll>
        </Section>

        {(trending.isLoading || (trending.data && trending.data.length > 0)) && (
          <Section title={`Tendances · ${seasonLabel()}`}>
            <HorizontalScroll>
              <CardList data={trending.data} isLoading={trending.isLoading} />
            </HorizontalScroll>
          </Section>
        )}

        {hasLive && live.data && (
          <div id="films-series" className="scroll-mt-24 pb-6">
            <LiveHome data={live.data} />
          </div>
        )}
      </main>

      <Footer />
    </motion.div>
  );
}
