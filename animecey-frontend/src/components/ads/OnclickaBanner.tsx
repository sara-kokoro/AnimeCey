import { ONCLICKA } from "@/config/ads";
import { cn } from "@/lib/utils";

/**
 * Emplacement de la bannière OnClicka (spot « banner #1 »). Rien n'est affiché sans code OnClicka
 * ou sans pub disponible : le cadre reste vide et ne prend aucune place.
 */
export function OnclickaBanner({ className }: { className?: string }) {
  if (!ONCLICKA.bannerId || !ONCLICKA.loader.trim()) return null;
  return (
    <div className={cn("flex justify-center overflow-hidden", className)}>
      <div data-banner-id={ONCLICKA.bannerId} />
    </div>
  );
}
