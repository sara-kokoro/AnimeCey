import { AnimeCard } from "@/components/anime/AnimeCard";
import { SkeletonCard } from "@/components/ui/SkeletonCard";
import type { Anime } from "@/types";

/** Les N premiers ont un chiffre plein ; les suivants un chiffre en contour. */
const SOLID_COUNT = 3;

export function RankedRow({ data, isLoading }: { data?: Anime[]; isLoading: boolean }) {
  if (isLoading) return <>{Array.from({ length: 6 }).map((_, i) => <SkeletonCard key={i} />)}</>;
  if (!data || data.length === 0) return null;
  return (
    <>
      {data.slice(0, 10).map((a, i) => {
        const solid = i < SOLID_COUNT;
        return (
          <div key={a.id} className="relative shrink-0 flex items-end">
            <span
              aria-hidden
              className={
                "font-display font-extrabold leading-[0.8] select-none -mr-5 md:-mr-6 mb-14 md:mb-16 " +
                "text-[104px] md:text-[132px] " +
                (solid ? "text-primary" : "text-transparent")
              }
              style={solid ? undefined : { WebkitTextStroke: "2px hsl(var(--primary))" }}
            >
              {i + 1}
            </span>
            <div className="relative z-10">
              <AnimeCard anime={a} index={i} />
            </div>
          </div>
        );
      })}
    </>
  );
}
