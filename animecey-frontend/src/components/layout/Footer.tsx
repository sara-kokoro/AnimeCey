import { Link } from "react-router-dom";

export function Footer() {
  return (
    <footer className="mt-24 border-t border-border bg-background">
      <div className="mx-auto max-w-7xl px-4 md:px-6 py-12 flex flex-col md:flex-row gap-6 md:items-center md:justify-between">
        <div>
          <p className="font-display font-extrabold text-xl">
            Anime<span className="text-primary">Cey</span>
          </p>
          <p className="text-sm text-muted-foreground font-body mt-1">
            Streaming d'animés en VF & VOSTFR.
          </p>
        </div>
        <nav className="flex flex-wrap gap-x-6 gap-y-2 text-sm font-body text-muted-foreground">
          <Link to="/catalogue" className="hover:text-foreground transition-colors">Catalogue</Link>
          <Link to="/genres" className="hover:text-foreground transition-colors">Genres</Link>
          <Link to="/legal" className="hover:text-foreground transition-colors">Mentions légales</Link>
          <Link to="/contact" className="hover:text-foreground transition-colors">Contact</Link>
        </nav>
        <p className="text-xs font-body text-muted-dim">
          © {new Date().getFullYear()} AnimeCey
        </p>
      </div>
    </footer>
  );
}