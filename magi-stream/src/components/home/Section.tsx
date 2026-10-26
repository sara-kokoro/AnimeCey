import { ChevronRight } from "lucide-react";
import { Link } from "@/lib/router";
import type { ReactNode } from "react";

interface Props {
  title: ReactNode;
  /** Lien « Voir tout » : affiché seulement s'il est fourni. */
  href?: string;
  children: ReactNode;
}

export function Section({ title, href, children }: Props) {
  return (
    <section className="mt-12 md:mt-14">
      <div className="flex items-end justify-between mb-4">
        <h2 className="font-display font-bold text-xl md:text-2xl text-foreground flex items-center gap-2.5">
          <span aria-hidden className="w-1 md:w-1.5 h-6 md:h-7 rounded-full bg-primary shrink-0" />
          {title}
        </h2>
        {href && (
          <Link
            to={href}
            className="inline-flex items-center gap-1 text-sm font-body font-semibold text-primary hover:text-primary-dim transition-colors"
          >
            Voir tout
            <ChevronRight className="w-4 h-4" />
          </Link>
        )}
      </div>
      {children}
    </section>
  );
}
