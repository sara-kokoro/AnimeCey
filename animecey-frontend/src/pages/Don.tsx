import { HeartHandshake } from "lucide-react";
import { Navbar } from "@/components/layout/Navbar";
import { Footer } from "@/components/layout/Footer";
import { Seo } from "@/components/Seo";
import { DonateCard } from "@/components/donate/DonateCard";

export default function Don() {
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

        <DonateCard className="mt-6" />
      </main>
      <Footer />
    </div>
  );
}
