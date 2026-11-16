import { HeartHandshake } from "lucide-react";
import { Navbar } from "@/components/layout/Navbar";
import { Footer } from "@/components/layout/Footer";
import { Seo } from "@/components/Seo";
import { Suspense, lazy } from "react";
import { Loader2 } from "lucide-react";
import { MobileMoneyDonation } from "@/components/donate/MobileMoneyDonation";

const DonateCard = lazy(() => import("@/components/donate/DonateCard").then((m) => ({ default: m.DonateCard })));

function CryptoLoading() {
  return (
    <div className="mt-3 rounded-3xl border border-border bg-surface p-6 flex flex-col items-center gap-2 text-center">
      <Loader2 className="w-7 h-7 animate-spin text-primary" />
      <p className="text-sm font-bold">Chargement…</p>
      <p className="text-xs text-muted-foreground">Préparation des adresses crypto.</p>
    </div>
  );
}

export default function Don() {
  return (
    <div className="min-h-screen bg-background">
      <Seo title="Faire un don | Magi-Stream" description="Soutiens Magi-Stream : ton don nous aide à garder le service gratuit." path="/donate" />
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

        <MobileMoneyDonation className="mt-6" />

        <h2 className="mt-8 font-display font-bold text-lg">Ou en cryptomonnaie</h2>
        <Suspense fallback={<CryptoLoading />}>
          <DonateCard className="mt-3" />
        </Suspense>
      </main>
      <Footer />
    </div>
  );
}
