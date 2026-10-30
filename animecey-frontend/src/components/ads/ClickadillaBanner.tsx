import { CLICKADILLA } from "@/config/ads";
import { cn } from "@/lib/utils";

/**
 * Emplacement de la bannière Clickadilla (spot « Banner #1 »).
 * Le script chargé par <ClickadillaAd /> remplit ce cadre ; sans pub, il reste vide.
 */
export function ClickadillaBanner({ className }: { className?: string }) {
  if (!CLICKADILLA.bannerId) return null;
  return (
    <div className={cn("flex justify-center overflow-hidden", className)}>
      <div data-banner-id={CLICKADILLA.bannerId} />
    </div>
  );
}
