import { Link } from "react-router-dom";
import { motion } from "framer-motion";
import { Navbar } from "@/components/layout/Navbar";
import { Footer } from "@/components/layout/Footer";
import { allGenres, animes } from "@/data/mock";

export default function Genres() {
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

        <div className="mt-8 grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-3">
          {allGenres.map((g, i) => {
            const count = animes.filter((a) => a.genres.includes(g)).length;
            return (
              <motion.div
                key={g}
                initial={{ opacity: 0, y: 12 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: i * 0.03 }}
              >
                <Link
                  to={`/genre/${encodeURIComponent(g)}`}
                  className="group block rounded-xl bg-surface border border-border-subtle p-4 hover:border-primary/40 hover:bg-surface-2 transition-all"
                >
                  <p className="font-display font-bold text-base text-foreground group-hover:text-primary transition-colors">
                    {g}
                  </p>
                  <p className="text-xs text-muted-foreground font-body mt-1">
                    {count} titre{count > 1 ? "s" : ""}
                  </p>
                </Link>
              </motion.div>
            );
          })}
        </div>
      </main>
      <Footer />
    </motion.div>
  );
}