import { useQuery } from "@tanstack/react-query";
import { Navbar } from "@/components/layout/Navbar";
import { Footer } from "@/components/layout/Footer";
import { HeroCarousel } from "@/components/home/HeroCarousel";
import { Section } from "@/components/home/Section";
import { HorizontalScroll } from "@/components/ui/HorizontalScroll";
import { AnimeCard } from "@/components/anime/AnimeCard";
import { SkeletonCard } from "@/components/ui/SkeletonCard";
import { fetchFeatured, fetchTopWeek, fetchTopRated, fetchLatest, fetchTrending } from "@/api/animes";
import { motion } from "framer-motion";

function CardList({ data, isLoading }: { data?: unknown[]; isLoading: boolean }) {
  if (isLoading) return <>{Array.from({ length: 6 }).map((_, i) => <SkeletonCard key={i} />)}</>;
  if (!data || data.length === 0) return <p className="text-muted-foreground text-sm">Aucun résultat</p>;
  return <>{(data as Record<string, unknown>[]).map((a, i) => <AnimeCard key={String(a.id)} anime={a as never} index={i} />)}</>;
}

export default function Home() {
  const topWeek = useQuery({ queryKey: ["top-week"], queryFn: fetchTopWeek });
  const topRated = useQuery({ queryKey: ["top-rated"], queryFn: fetchTopRated });
  const latest = useQuery({ queryKey: ["latest"], queryFn: fetchLatest });
  const trending = useQuery({ queryKey: ["trending"], queryFn: fetchTrending });

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
        <Section title="Top de la semaine">
          <HorizontalScroll>
            <CardList data={topWeek.data} isLoading={topWeek.isLoading} />
          </HorizontalScroll>
        </Section>

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

        <Section title="Tendances">
          <HorizontalScroll>
            <CardList data={trending.data} isLoading={trending.isLoading} />
          </HorizontalScroll>
        </Section>
      </main>

      <Footer />
    </motion.div>
  );
}
