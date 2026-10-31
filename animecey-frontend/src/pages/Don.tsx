import { useState } from "react";
import { Check, Copy, HeartHandshake, ShieldAlert } from "lucide-react";
import { toast } from "sonner";
import { Navbar } from "@/components/layout/Navbar";
import { Footer } from "@/components/layout/Footer";
import { Seo } from "@/components/Seo";
import { WALLETS } from "@/config/social";

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

export default function Don() {
  const [copied, setCopied] = useState<string | null>(null);

  const copy = async (id: string, address: string) => {
    if (await copyText(address)) {
      setCopied(id);
      toast.success("Adresse copiée");
      window.setTimeout(() => setCopied((c) => (c === id ? null : c)), 2000);
    } else {
      toast.error("Copie impossible : appuie longuement sur l'adresse pour la copier.");
    }
  };

  return (
    <div className="min-h-screen bg-background">
      <Seo title="Faire un don | Magi-Stream" description="Soutiens Magi-Stream : ton don nous aide à garder le service gratuit." path="/don" />
      <Navbar />
      <main className="pt-20 pb-10 mx-auto max-w-2xl px-4 md:px-6">
        <div className="flex items-center gap-3">
          <span className="w-12 h-12 rounded-2xl bg-primary/15 text-primary flex items-center justify-center">
            <HeartHandshake className="w-6 h-6" />
          </span>
          <h1 className="font-display font-extrabold text-2xl md:text-3xl">Faire un don</h1>
        </div>
        <p className="mt-4 text-[15px] leading-relaxed text-muted-foreground">
          Magi-Stream est gratuit, et on veut que ça reste comme ça. Chaque don nous aide à payer les serveurs, à
          ajouter plus d'animés au catalogue et à garder un service rapide et sans abonnement. Même un petit montant
          compte. Merci d'être là&nbsp;!
        </p>

        <ul className="mt-6 space-y-3">
          {WALLETS.map((w) => (
            <li key={w.id} className="rounded-2xl bg-surface border border-border-subtle p-4">
              <p className="font-display font-bold">{w.name}</p>
              <p className="text-xs text-muted-foreground mt-0.5">{w.networks}</p>
              <p className="mt-3 rounded-xl bg-background border border-border px-3 py-2.5 font-mono text-[13px] break-all select-all">
                {w.address}
              </p>
              <button
                onClick={() => void copy(w.id, w.address)}
                className="mt-3 inline-flex items-center gap-2 h-10 px-4 rounded-full bg-primary text-primary-foreground text-sm font-bold hover:bg-primary-dim transition-colors"
              >
                {copied === w.id ? <Check className="w-4 h-4" /> : <Copy className="w-4 h-4" />}
                {copied === w.id ? "Copié" : "Copier l'adresse"}
              </button>
            </li>
          ))}
        </ul>

        <p className="mt-5 flex gap-2 rounded-xl border border-border-subtle bg-surface/60 p-3 text-xs text-muted-foreground">
          <ShieldAlert className="w-4 h-4 shrink-0 text-highlight mt-0.5" />
          Envoie chaque monnaie uniquement sur le réseau indiqué. Un envoi sur un mauvais réseau est perdu et on ne peut
          pas le récupérer.
        </p>
      </main>
      <Footer />
    </div>
  );
}
