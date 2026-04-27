import { ChevronRight } from "lucide-react";
import { Link } from "react-router-dom";
import type { ReactNode } from "react";

interface Props {
  title: string;
  href?: string;
  children: ReactNode;
}

export function Section({ title, href = "/catalogue", children }: Props) {
  return (
    <section className="mt-12 md:mt-14">
      <div className="flex items-end justify-between mb-4">
        <h2 className="font-display font-bold text-xl md:text-2xl text-foreground">
          {title}
        </h2>
        <Link
          to={href}
          className="inline-flex items-center gap-1 text-sm font-body font-semibold text-primary hover:text-primary-dim transition-colors"
        >
          Voir tout
          <ChevronRight className="w-4 h-4" />
        </Link>
      </div>
      {children}
    </section>
  );
}