import { Mail, Megaphone, Send, Smartphone, Globe, Image as ImageIcon, CalendarClock, BarChart3 } from "lucide-react";
import { Navbar } from "@/components/layout/Navbar";
import { Footer } from "@/components/layout/Footer";
import { Seo } from "@/components/Seo";
import { ADVERTISE } from "@/config/contact";

const SLOTS = [
  "Page d'accueil : en haut et en bas de page",
  "Fiche de chaque animé, film et série",
  "Sous le lecteur vidéo",
  "Page « Mes téléchargements » et lecteur hors ligne",
  "Page hors connexion de l'application",
];

export default function Pub() {
  const mail = `mailto:${ADVERTISE.email}?subject=${encodeURIComponent("Pub sur Magi-Stream")}&body=${encodeURIComponent(
    "Bonjour,\n\nJe souhaite afficher une pub sur Magi-Stream.\n\nMon activité / lien :\nEmplacements souhaités :\nDurée (jours) :\n",
  )}`;
  return (
    <div className="min-h-screen bg-background">
      <Seo
        title="Affiche ta pub sur Magi-Stream"
        description="Augmente ta visibilité auprès des fans d'animés, de films et de séries : affiche ta pub sur le site et l'application Magi-Stream."
        path="/pub"
      />
      <Navbar />
      <main className="pt-20 pb-10 mx-auto max-w-2xl px-4 md:px-6">
        <div className="flex items-center gap-3">
          <span className="w-12 h-12 rounded-2xl bg-primary/15 text-primary flex items-center justify-center">
            <Megaphone className="w-6 h-6" />
          </span>
          <h1 className="font-display font-extrabold text-2xl md:text-3xl">Affiche ta pub ici</h1>
        </div>
        <p className="mt-4 text-[15px] leading-relaxed text-muted-foreground">
          Fais connaître ta chaîne, ton site, ta boutique ou ton service aux fans d'animés, de films et de séries qui
          viennent sur Magi-Stream, sur le site comme dans l'application Android. Ta pub s'affiche aux emplacements que
          tu choisis, pour la durée que tu veux.
        </p>

        <ul className="mt-6 grid gap-3">
          {[
            { icon: ImageIcon, title: "Image ou GIF", text: "Avec un texte et un bouton « Rejoindre » vers ton lien (facultatifs)." },
            { icon: Globe, title: "Site + application", text: "Une seule réservation, visible sur le site et dans l'app." },
            { icon: CalendarClock, title: "Durée au choix", text: "De quelques jours à plusieurs semaines." },
            { icon: BarChart3, title: "Chiffres à la fin", text: "Nombre de vues et de clics sur ta pub." },
          ].map((f) => (
            <li key={f.title} className="flex items-start gap-3 rounded-2xl bg-surface border border-border-subtle p-4">
              <f.icon className="w-5 h-5 mt-0.5 text-primary shrink-0" />
              <div>
                <p className="font-display font-bold text-sm">{f.title}</p>
                <p className="text-sm text-muted-foreground">{f.text}</p>
              </div>
            </li>
          ))}
        </ul>

        <h2 className="mt-8 font-display font-bold text-lg inline-flex items-center gap-2">
          <Smartphone className="w-5 h-5 text-primary" /> Où ta pub apparaît
        </h2>
        <ul className="mt-3 space-y-1.5 text-sm text-muted-foreground list-disc pl-5">
          {SLOTS.map((s) => (
            <li key={s}>{s}</li>
          ))}
        </ul>
        <p className="mt-3 text-sm text-muted-foreground">Un emplacement, plusieurs, ou tous : c'est toi qui choisis.</p>

        <div className="mt-8 rounded-3xl border border-primary/40 bg-primary/10 p-5">
          <p className="font-display font-extrabold text-lg">Contacte-nous</p>
          <p className="mt-1 text-sm text-muted-foreground">Écris-nous avec ton lien et les emplacements souhaités : on te répond vite.</p>
          <div className="mt-4 grid gap-2.5">
            <a
              href={ADVERTISE.telegramUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="flex h-12 items-center justify-center gap-2 rounded-2xl bg-primary text-primary-foreground font-bold hover:bg-primary-dim transition-colors"
            >
              <Send className="w-5 h-5" /> Telegram {ADVERTISE.telegramName}
            </a>
            <a
              href={mail}
              className="flex h-12 items-center justify-center gap-2 rounded-2xl border border-border bg-background font-bold hover:border-primary/50 transition-colors"
            >
              <Mail className="w-5 h-5" /> {ADVERTISE.email}
            </a>
          </div>
        </div>
      </main>
      <Footer />
    </div>
  );
}
