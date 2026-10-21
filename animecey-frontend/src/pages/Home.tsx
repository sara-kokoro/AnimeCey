import { useQuery } from "@tanstack/react-query";
import { Link } from "@/lib/router";
import { Flame, Sparkles, Star, Film } from "lucide-react";
import type { ReactNode } from "react";
import { Navbar } from "@/components/layout/Navbar";
import { Footer } from "@/components/layout/Footer";
import { Seo } from "@/components/Seo";
import { HeroCarousel } from "@/components/home/HeroCarousel";
import { Section } from "@/components/home/Section";
import { HorizontalScroll } from "@/components/ui/HorizontalScroll";
import { RankedRow } from "@/components/home/RankedRow";
import { LiveHome } from "@/components/home/LiveHome";
import { LatestReleasesRail } from "@/components/home/LatestReleasesRail";
import { AnimeCard } from "@/components/anime/AnimeCard";
import { SkeletonCard } from "@/components/ui/SkeletonCard";
import { AdsterraBanner } from "@/components/ads/AdsterraBanner";
import { SocialBarAd } from "@/components/ads/SocialBarAd";
import { fetchAnimes, fetchLiveHome, fetchTopWeek, fetchTopRated, fetchLatest, fetchTrending } from "@/api/animes";
import type { Anime } from "@/types";

const SITE = "https://www.magi-stream.online";
const SEASON_NAMES = ["Hiver", "Hiver", "Hiver", "Printemps", "Printemps", "Printemps", "Été", "Été", "Été", "Automne", "Automne", "Automne"];
const seasonLabel = () => `${SEASON_NAMES[new Date().getMonth()]} ${new Date().getFullYear()}`;

/** Rangée horizontale (défilement tactile avec accroche) */
function Row({ data, isLoading }: { data?: Anime[]; isLoading: boolean }) {
  if (isLoading) return <>{Array.from({ length: 6 }).map((_, i) => <SkeletonCard key={i} />)}</>;
  if (!data || data.length === 0) return <p className="text-muted-foreground text-sm">Aucun résultat</p>;
  return <>{data.slice(0, 12).map((a, i) => <AnimeCard key={a.id} anime={a} index={i} />)}</>;
}

function Title({ icon, children }: { icon: ReactNode; children: ReactNode }) {
  return <span className="inline-flex items-center gap-2">{icon}{children}</span>;
}

export default function Home() {
  const topWeek = useQuery({ queryKey: ["top-week"], queryFn: fetchTopWeek });
  const topRated = useQuery({ queryKey: ["top-rated"], queryFn: fetchTopRated });
  const latest = useQuery({ queryKey: ["latest"], queryFn: fetchLatest });
  const trending = useQuery({ queryKey: ["trending"], queryFn: fetchTrending });
  const filmsJp = useQuery({
    queryKey: ["films-japanime"],
    queryFn: () => fetchAnimes({ type: "film", category: "anime", sort: "recent", limit: 12 }),
    staleTime: 60_000,
  });
  const live = useQuery({ queryKey: ["live-home"], queryFn: fetchLiveHome, staleTime: 60_000 });
  const hasLive = !!live.data && (live.data.featured.length > 0 || live.data.latest.length > 0);

  const jump = (id: string) => document.getElementById(id)?.scrollIntoView({ behavior: "smooth", block: "start" });

  // Données structurées : site + recherche, et liste des animés tendance
  const trendingList = (trending.data ?? topWeek.data ?? []).slice(0, 10);
  const jsonLd: Record<string, unknown>[] = [
    {
      "@context": "https://schema.org",
      "@type": "WebSite",
      name: "Magi-Stream",
      url: `${SITE}/`,
      inLanguage: "fr-FR",
      potentialAction: {
        "@type": "SearchAction",
        target: `${SITE}/search?q={search_term_string}`,
        "query-input": "required name=search_term_string",
      },
    },
    { "@context": "https://schema.org", "@type": "Organization", name: "Magi-Stream", url: `${SITE}/`, logo: `${SITE}/apple-touch-icon.png` },
  ];
  if (trendingList.length > 0) {
    jsonLd.push({
      "@context": "https://schema.org",
      "@type": "ItemList",
      name: "Animés tendance",
      itemListElement: trendingList.map((a, i) => ({
        "@type": "ListItem",
        position: i + 1,
        url: `${SITE}/anime/${a.id}`,
        name: a.title,
        image: a.poster_url,
      })),
    });
  }

  return (
    <div className="min-h-screen bg-background overflow-x-hidden">
      <Seo
        title="Magi-Stream : streaming d'animés, films et séries en VF et VOSTFR"
        description="Regarde tes animés, films et séries préférés en streaming gratuit, en VF et VOSTFR, sur Magi-Stream. Derniers épisodes, top de la semaine, tendances de la saison et watchlist."
        path="/"
        jsonLd={jsonLd}
      />
      <Navbar />
      <h1 className="sr-only">Magi-Stream : streaming d'animés, films et séries en VF et VOSTFR</h1>
      <HeroCarousel />

      <main className="mx-auto max-w-7xl px-3 md:px-6">
        <SocialBarAd />

        <nav aria-label="Sections" className="mt-2 flex gap-2 overflow-x-auto no-scrollbar -mx-3 px-3 md:mx-0 md:px-0">
          <button onClick={() => jump("animes")} className="shrink-0 px-4 py-2 rounded-full bg-primary text-primary-foreground text-sm font-semibold">
            Animés
          </button>
          {hasLive && (
            <button onClick={() => jump("films-series")} className="shrink-0 px-4 py-2 rounded-full bg-surface border border-border-subtle text-sm font-semibold hover:bg-surface-2 transition-colors">
              Films &amp; Séries
            </button>
          )}
          {[
            { to: "/catalogue", label: "Catalogue" },
            { to: "/calendrier", label: "Calendrier" },
            { to: "/genres", label: "Genres" },
          ].map((l) => (
            <Link key={l.to} to={l.to} className="shrink-0 px-4 py-2 rounded-full bg-surface border border-border-subtle text-sm font-semibold hover:bg-surface-2 transition-colors">
              {l.label}
            </Link>
          ))}
        </nav>

        <LatestReleasesRail />

        <AdsterraBanner format="banner" className="mt-4 mb-2" />
        <div id="animes" className="scroll-mt-24" />


        {(trending.isLoading || (trending.data && trending.data.length > 0)) && (
          <Section title={<Title icon={<Flame className="w-5 h-5 text-primary" />}>{`Tendances · ${seasonLabel()}`}</Title>} href="/catalogue?sort=score">
            <HorizontalScroll>
              <Row data={trending.data} isLoading={trending.isLoading} />
            </HorizontalScroll>
          </Section>
        )}

        {(topWeek.isLoading || (topWeek.data && topWeek.data.length > 0)) && (
          <Section title="Top 10 de la semaine">
            <HorizontalScroll>
              <RankedRow data={topWeek.data} isLoading={topWeek.isLoading} />
            </HorizontalScroll>
          </Section>
        )}

        <Section title={<Title icon={<Sparkles className="w-5 h-5 text-primary" />}>Derniers ajouts</Title>} href="/catalogue?sort=recent">
          <HorizontalScroll>
            <Row data={latest.data} isLoading={latest.isLoading} />
          </HorizontalScroll>
        </Section>

        <AdsterraBanner format="native" className="my-8" />

        <Section title={<Title icon={<Star className="w-5 h-5 text-primary" />}>Les mieux notés</Title>} href="/catalogue?sort=score">
          <HorizontalScroll>
            <Row data={topRated.data} isLoading={topRated.isLoading} />
          </HorizontalScroll>
        </Section>

        {(filmsJp.isLoading || (filmsJp.data && filmsJp.data.items.length > 0)) && (
          <Section title={<Title icon={<Film className="w-5 h-5 text-primary" />}>Films Japanime</Title>} href="/films-japanime">
            <HorizontalScroll>
              <Row data={filmsJp.data?.items} isLoading={filmsJp.isLoading} />
            </HorizontalScroll>
          </Section>
        )}

        {hasLive && live.data && (
          <div id="films-series" className="scroll-mt-24 pb-6">
            <LiveHome data={live.data} />
          </div>
        )}

        <section className="mt-14 mb-10 text-sm text-muted-foreground font-body max-w-3xl">
          <h2 className="font-display font-bold text-lg text-foreground mb-2">Streaming d'animés en VF et VOSTFR</h2>
          <p>
            Magi-Stream te permet de regarder tes animés, films et séries en streaming, en version française (VF) ou
            sous-titrée (VOSTFR). Retrouve les derniers épisodes, le top de la semaine, les tendances de la saison, le
            calendrier des sorties et une watchlist pour ne rien rater.
          </p>
        </section>
      </main>

      <Footer />
    </div>
  );
}
