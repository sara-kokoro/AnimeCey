import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { motion } from "framer-motion";
import { Loader2 } from "lucide-react";
import { Navbar } from "@/components/layout/Navbar";
import { Footer } from "@/components/layout/Footer";
import { fetchAnimes } from "@/api/animes";

const ALL_GENRES = [
  "Action", "Aventure", "Comédie", "Drame", "Fantasy", "Horreur",
  "Mystère", "Romance", "Sci-Fi", "Shonen", "Seinen", "Slice of Life",
  "Sports", "Surnaturel", "Thriller", "Mecha", "Isekai", "Musique",
  "Psychologique", "Ecchi",
];

export default function Genres() {
  const { data, isLoading } = useQuery({
    queryKey: ["animes-for-genres"],
    queryFn: () => fetchAnimes({ limit: 200 }),
    staleTime: 60_000,
  });

  const animes = data?.items ?? [];

  const genresWithCount = ALL_GENRES.map((g) => ({
    name: g,
    count: animes.filter((a) => a.genres?.some((ag: string) => ag.toLowerCase() === g.toLowerCase())).length,
  })).sort((a, b) => b.count - a.count);

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.35 }}
      className="min-h-screen bg-background"
    >
      <Navbar />
      <main className="pt-24 md:pt-28 pb-20 mx-auto max-w-7xl px-4 md:px-6">
        <h1 className="font-display font-extrabold text-3xl md:text-4xl">Genres</h1>
        <p className="text-sm text-muted-foreground font-body mt-2 max-w-2xl">
          Explore les univers — de l'action effrénée aux drames intimes.
        </p>

        {isLoading ? (
          <div className="flex justify-center py-12"><Loader2 className="w-6 h-6 animate-spin text-primary" /></div>
        ) : (
          <div className="mt-8 grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-3">
            {genresWithCount.map((g, i) => (
              <motion.div
                key={g.name}
                initial={{ opacity: 0, y: 12 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: i * 0.03 }}
              >
                <Link
                  to={`/genre/${encodeURIComponent(g.name)}`}
                  className="group block rounded-xl bg-surface border border-border-subtle p-4 hover:border-primary/40 hover:bg-surface-2 transition-all"
                >
                  <p className="font-display font-bold text-base text-foreground group-hover:text-primary transition-colors">
                    {g.name}
                  </p>
                  <p className="text-xs text-muted-foreground font-body mt-1">
                    {g.count} titre{g.count > 1 ? "s" : ""}
                  </p>
                </Link>
              </motion.div>
            ))}
          </div>
        )}
      </main>
      <Footer />
    </motion.div>
  );
}
