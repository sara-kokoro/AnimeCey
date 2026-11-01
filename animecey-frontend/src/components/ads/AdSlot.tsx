import { useEffect, useRef } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link } from "@/lib/router";
import { Megaphone } from "lucide-react";
import { fetchAd, reportAdView, type AdSlotKey } from "@/api/ads";
import { cn } from "@/lib/utils";

/**
 * Emplacement de pub manuelle (pubs créées avec /pub dans le bot).
 * - une pub est en cours pour cet emplacement : image ou GIF, avec texte (en citation) et bouton facultatifs ;
 * - sinon : une invitation « Affiche ta pub ici » qui mène à la page /pub (contact annonceurs).
 * La vue est comptée une seule fois, quand l'emplacement apparaît à l'écran ; le clic est compté par le serveur.
 */
export function AdSlot({ slot, className }: { slot: AdSlotKey; className?: string }) {
  const { data } = useQuery({
    queryKey: ["ad", slot],
    queryFn: () => fetchAd(slot),
    staleTime: 5 * 60_000,
    retry: false,
  });
  const ref = useRef<HTMLDivElement>(null);
  const counted = useRef<number | null>(null);
  const ad = data?.ad ?? null;

  useEffect(() => {
    if (!ad || !ref.current || counted.current === ad.id) return;
    const io = new IntersectionObserver(
      ([e]) => {
        if (e.isIntersecting && counted.current !== ad.id) {
          counted.current = ad.id;
          void reportAdView(ad.id, slot).catch(() => undefined);
          io.disconnect();
        }
      },
      { threshold: 0.4 },
    );
    io.observe(ref.current);
    return () => io.disconnect();
  }, [ad, slot]);

  if (!data) return null; // chargement, ou serveur injoignable : rien à afficher

  if (!ad) {
    return (
      <div className={cn("mx-auto max-w-3xl", className)}>
        <Link
          to="/pub"
          className="flex items-center gap-3 rounded-2xl border border-dashed border-border bg-surface/40 px-4 py-3 hover:border-primary/50 hover:bg-surface/70 transition-colors"
        >
          <span className="shrink-0 w-10 h-10 rounded-xl bg-primary/15 text-primary flex items-center justify-center">
            <Megaphone className="w-5 h-5" />
          </span>
          <span className="min-w-0 flex-1">
            <span className="block font-display font-bold text-sm">Affiche ta pub ici</span>
            <span className="block text-xs text-muted-foreground">
              Augmente ta visibilité avec Magi-Stream : contacte-nous pour réserver cet emplacement.
            </span>
          </span>
          <span className="shrink-0 text-xs font-bold text-primary">Voir</span>
        </Link>
      </div>
    );
  }

  const isVideo = ad.mime.startsWith("video/");
  return (
    <div ref={ref} className={cn("mx-auto max-w-3xl", className)}>
      <div className="overflow-hidden rounded-2xl border border-border-subtle bg-surface">
        <a href={ad.link} target="_blank" rel="noopener noreferrer sponsored" className="relative block bg-black/30">
          {isVideo ? (
            <video src={ad.media_url} autoPlay loop muted playsInline className="w-full max-h-[320px] object-contain" />
          ) : (
            <img src={ad.media_url} alt="Publicité" loading="lazy" className="w-full max-h-[320px] object-contain" />
          )}
          <span className="absolute top-2 left-2 rounded bg-black/70 px-1.5 py-0.5 text-[10px] font-semibold text-white">
            Publicité
          </span>
        </a>
        {(ad.text || (ad.button_text && ad.button_link)) && (
          <div className="p-3">
            {ad.text && (
              <blockquote className="border-l-4 border-primary pl-3 text-sm text-foreground/90 whitespace-pre-line">
                {ad.text}
              </blockquote>
            )}
            {ad.button_text && ad.button_link && (
              <a
                href={ad.button_link}
                target="_blank"
                rel="noopener noreferrer sponsored"
                className="mt-3 flex h-11 items-center justify-center rounded-full bg-primary text-primary-foreground font-bold hover:bg-primary-dim transition-colors"
              >
                {ad.button_text}
              </a>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
