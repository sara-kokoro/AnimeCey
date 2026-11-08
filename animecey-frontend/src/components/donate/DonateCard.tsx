import { useState } from "react";
import { Check, ChevronDown, Copy, ShieldAlert } from "lucide-react";
import { toast } from "sonner";
import { WALLETS } from "@/config/social";
import { LottieCoin } from "./LottieCoin";

const COIN: Record<string, string> = { ton: "ton", evm: "eth", sol: "sol", tron: "tron", btc: "btc" };

async function copyText(text: string): Promise<boolean> {
  try {
    await navigator.clipboard.writeText(text);
    return true;
  } catch {
    try {
      const ta = document.createElement("textarea");
      ta.value = text;
      ta.style.position = "fixed";
      ta.style.opacity = "0";
      document.body.appendChild(ta);
      ta.select();
      const ok = document.execCommand("copy");
      ta.remove();
      return ok;
    } catch {
      return false;
    }
  }
}

function Heart({ className = "" }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" className={className} aria-hidden>
      <path
        fill="currentColor"
        d="M12 21.35l-1.45-1.32C5.4 15.36 2 12.28 2 8.5 2 5.42 4.42 3 7.5 3c1.74 0 3.41.81 4.5 2.09C13.09 3.81 14.76 3 16.5 3 19.58 3 22 5.42 22 8.5c0 3.78-3.4 6.86-8.55 11.54L12 21.35z"
      />
    </svg>
  );
}

/** Carte « cagnotte » : message clair + adresses (dépliables en version compacte). */
export function DonateCard({ compact = false, className = "" }: { compact?: boolean; className?: string }) {
  const [open, setOpen] = useState(!compact);
  const [copied, setCopied] = useState<string | null>(null);

  const copy = async (id: string, address: string) => {
    if (await copyText(address)) {
      setCopied(id);
      toast.success("Adresse copiée. Merci ❤️");
      window.setTimeout(() => setCopied((c) => (c === id ? null : c)), 2000);
    } else {
      toast.error("Copie impossible : appuie longuement sur l'adresse pour la copier.");
    }
  };

  return (
    <section className={`rounded-3xl border border-primary/40 bg-gradient-to-br from-primary/15 via-primary/5 to-transparent p-4 ${className}`}>
      <div className="flex items-center gap-3">
        <span className="shrink-0 w-12 h-12 rounded-2xl bg-primary text-primary-foreground flex items-center justify-center">
          <Heart className="w-6 h-6 animate-pulse" />
        </span>
        <div className="min-w-0 flex-1">
          <h2 className="font-display font-extrabold text-base leading-snug">Fais-nous un don ❤️</h2>
          <p className="mt-0.5 text-xs text-muted-foreground leading-snug">
            Ça nous aide à améliorer Magi-Stream et à le garder en ligne, gratuit pour tout le monde.
          </p>
        </div>
      </div>

      {compact && (
        <button
          onClick={() => setOpen((o) => !o)}
          aria-expanded={open}
          className="mt-3 w-full h-11 rounded-full bg-primary text-primary-foreground text-sm font-bold inline-flex items-center justify-center gap-2"
        >
          {open ? "Masquer" : "Participer à la cagnotte"}
          <ChevronDown className={`w-4 h-4 transition-transform ${open ? "rotate-180" : ""}`} />
        </button>
      )}

      {open && (
        <>
          <ul className="mt-3 space-y-2.5">
            {WALLETS.map((w) => (
              <li key={w.id} className="rounded-2xl bg-surface border border-border-subtle p-3">
                <div className="flex items-center gap-3">
                  <LottieCoin coin={COIN[w.id] ?? "btc"} />
                  <div className="min-w-0">
                    <p className="font-display font-bold leading-tight">{w.name}</p>
                    <p className="text-xs text-muted-foreground">{w.networks}</p>
                  </div>
                </div>
                <p className="mt-2.5 rounded-xl bg-background border border-border px-3 py-2 font-mono text-[12px] break-all select-all">
                  {w.address}
                </p>
                <button
                  onClick={() => void copy(w.id, w.address)}
                  className="mt-2.5 inline-flex items-center gap-2 h-10 px-4 rounded-full bg-primary text-primary-foreground text-sm font-bold hover:bg-primary-dim transition-colors"
                >
                  {copied === w.id ? <Check className="w-4 h-4" /> : <Copy className="w-4 h-4" />}
                  {copied === w.id ? "Copié" : "Copier l'adresse"}
                </button>
              </li>
            ))}
          </ul>
          <p className="mt-3 flex gap-2 text-xs text-muted-foreground">
            <ShieldAlert className="w-4 h-4 shrink-0 text-highlight mt-0.5" />
            Envoie chaque monnaie uniquement sur le réseau indiqué : un mauvais réseau fait perdre l'envoi.
          </p>
        </>
      )}
    </section>
  );
}
