import { useState } from "react";
import { Check, ChevronDown, Copy, ShieldAlert } from "lucide-react";
import { toast } from "sonner";
import { WALLETS } from "@/config/social";
import { LottieCoin } from "./LottieCoin";

const ADDR = Object.fromEntries(WALLETS.map((w) => [w.id, w.address])) as Record<string, string>;

/** USDT : un seul jeton, plusieurs réseaux. Chaque réseau pointe vers l'adresse du bon portefeuille. */
const USDT_NETWORKS = [
  { id: "trc20", label: "Tron (TRC-20)", address: ADDR.tron, note: "Le moins cher : recommandé." },
  { id: "bep20", label: "BNB Chain (BEP-20)", address: ADDR.evm, note: "Réseau BNB Smart Chain." },
  { id: "erc20", label: "Ethereum (ERC-20)", address: ADDR.evm, note: "Frais plus élevés." },
  { id: "sol", label: "Solana", address: ADDR.sol, note: "Réseau Solana." },
  { id: "ton", label: "TON", address: ADDR.ton, note: "USDT sur le réseau TON." },
  { id: "evm", label: "Polygon · Arbitrum · Base · Avalanche", address: ADDR.evm, note: "Autres réseaux compatibles Ethereum." },
];

/** Autres actifs : on envoie la monnaie native de chaque réseau. */
const ASSETS = [
  { id: "btc", coin: "btc", name: "Bitcoin (BTC)", network: "Réseau Bitcoin", address: ADDR.btc },
  { id: "ton", coin: "ton", name: "TON", network: "Réseau TON", address: ADDR.ton },
  { id: "trx", coin: "tron", name: "Tron (TRX)", network: "Réseau Tron", address: ADDR.tron },
  { id: "eth", coin: "eth", name: "Ethereum (ETH)", network: "Ethereum, Base, Arbitrum…", address: ADDR.evm },
  { id: "bnb", coin: "bnb", name: "BNB", network: "BNB Chain", address: ADDR.evm },
  { id: "sol", coin: "sol", name: "Solana (SOL)", network: "Réseau Solana", address: ADDR.sol },
];

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
  const [net, setNet] = useState(USDT_NETWORKS[0].id);
  const usdt = USDT_NETWORKS.find((n) => n.id === net) ?? USDT_NETWORKS[0];

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
          {/* USDT */}
          <div className="mt-3 rounded-2xl bg-surface border border-border-subtle p-3">
            <div className="flex items-center gap-3">
              <LottieCoin coin="usdt" />
              <div className="min-w-0">
                <p className="font-display font-bold leading-tight">USDT (Tether)</p>
                <p className="text-xs text-muted-foreground">Choisis le réseau sur lequel tu envoies</p>
              </div>
            </div>
            <div className="mt-3 flex flex-wrap gap-2">
              {USDT_NETWORKS.map((n) => (
                <button
                  key={n.id}
                  type="button"
                  onClick={() => setNet(n.id)}
                  className={`h-9 px-3 rounded-full border text-xs font-bold transition-colors ${net === n.id ? "bg-primary text-primary-foreground border-primary" : "bg-background border-border hover:border-primary/60"}`}
                >
                  {n.label}
                </button>
              ))}
            </div>
            <p className="mt-2 text-xs text-muted-foreground">{usdt.note}</p>
            <p className="mt-2 rounded-xl bg-background border border-border px-3 py-2 font-mono text-[12px] break-all select-all">{usdt.address}</p>
            <button
              onClick={() => void copy(`usdt-${usdt.id}`, usdt.address)}
              className="mt-2.5 inline-flex items-center gap-2 h-10 px-4 rounded-full bg-primary text-primary-foreground text-sm font-bold hover:bg-primary-dim transition-colors"
            >
              {copied === `usdt-${usdt.id}` ? <Check className="w-4 h-4" /> : <Copy className="w-4 h-4" />}
              {copied === `usdt-${usdt.id}` ? "Copié" : "Copier l'adresse"}
            </button>
          </div>

          {/* Autres actifs */}
          <h3 className="mt-4 text-xs font-bold uppercase tracking-wide text-muted-foreground">Autres cryptos</h3>
          <ul className="mt-2 space-y-2.5">
            {ASSETS.map((a) => (
              <li key={a.id} className="rounded-2xl bg-surface border border-border-subtle p-3">
                <div className="flex items-center gap-3">
                  <LottieCoin coin={a.coin} />
                  <div className="min-w-0">
                    <p className="font-display font-bold leading-tight">{a.name}</p>
                    <p className="text-xs text-muted-foreground">{a.network}</p>
                  </div>
                </div>
                <p className="mt-2.5 rounded-xl bg-background border border-border px-3 py-2 font-mono text-[12px] break-all select-all">{a.address}</p>
                <button
                  onClick={() => void copy(a.id, a.address)}
                  className="mt-2.5 inline-flex items-center gap-2 h-10 px-4 rounded-full bg-primary text-primary-foreground text-sm font-bold hover:bg-primary-dim transition-colors"
                >
                  {copied === a.id ? <Check className="w-4 h-4" /> : <Copy className="w-4 h-4" />}
                  {copied === a.id ? "Copié" : "Copier l'adresse"}
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
