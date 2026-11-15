import { useEffect, useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { AnimatePresence, motion } from "framer-motion";
import { ExternalLink, Loader2, ShieldCheck, Smartphone } from "lucide-react";
import { createDonation, fetchDonateConfig, fetchDonationStatus } from "@/api/donate";

const LS_KEY = "magi:donation";
const fmt = (n: number) => n.toLocaleString("fr-FR").replace(/ | /g, " ");

function load(): { id: string; url?: string } | null {
  try {
    const raw = localStorage.getItem(LS_KEY);
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
}
function save(v: { id: string; url?: string } | null) {
  try {
    if (v) localStorage.setItem(LS_KEY, JSON.stringify(v));
    else localStorage.removeItem(LS_KEY);
  } catch {
    /* stockage indisponible : sans importance */
  }
}

/* ── Animations ─────────────────────────────────────────────────────── */

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

/** Attente : un cœur qui bat au centre d'ondes qui s'étendent. */
function WaitingAnimation() {
  return (
    <div className="relative mx-auto h-40 w-40 flex items-center justify-center">
      {[0, 1, 2].map((i) => (
        <motion.span
          key={i}
          className="absolute inset-0 rounded-full border-2 border-primary/50"
          initial={{ scale: 0.3, opacity: 0.8 }}
          animate={{ scale: 1.15, opacity: 0 }}
          transition={{ duration: 2.4, repeat: Infinity, delay: i * 0.8, ease: "easeOut" }}
        />
      ))}
      <motion.div
        className="relative flex h-20 w-20 items-center justify-center rounded-full bg-primary text-primary-foreground shadow-lg"
        animate={{ scale: [1, 1.12, 1] }}
        transition={{ duration: 1.2, repeat: Infinity, ease: "easeInOut" }}
      >
        <Heart className="h-9 w-9" />
      </motion.div>
    </div>
  );
}

const CONFETTI_COLORS = ["#a78bfa", "#f472b6", "#fbbf24", "#34d399", "#60a5fa", "#fb7185"];

/** Succès : pluie de confettis + cœurs qui montent, puis le cœur central. */
function SuccessAnimation() {
  const pieces = useMemo(
    () =>
      Array.from({ length: 46 }, (_, i) => ({
        id: i,
        x: (Math.random() - 0.5) * 320,
        y: 120 + Math.random() * 160,
        rot: Math.random() * 720 - 360,
        delay: Math.random() * 0.25,
        size: 6 + Math.random() * 7,
        color: CONFETTI_COLORS[i % CONFETTI_COLORS.length],
        round: i % 3 === 0,
      })),
    [],
  );
  const hearts = useMemo(
    () => Array.from({ length: 9 }, (_, i) => ({ id: i, x: (Math.random() - 0.5) * 220, delay: 0.3 + Math.random() * 1.6, size: 14 + Math.random() * 14 })),
    [],
  );
  return (
    <div className="relative mx-auto h-44 w-full flex items-center justify-center overflow-visible">
      {pieces.map((p) => (
        <motion.span
          key={p.id}
          className="absolute left-1/2 top-1/2"
          style={{ width: p.size, height: p.size * (p.round ? 1 : 0.5), background: p.color, borderRadius: p.round ? "50%" : 2 }}
          initial={{ x: 0, y: 0, opacity: 1, rotate: 0, scale: 0.4 }}
          animate={{ x: p.x, y: [0, -90 - Math.random() * 40, p.y], opacity: [1, 1, 0], rotate: p.rot, scale: 1 }}
          transition={{ duration: 2.2, delay: p.delay, ease: "easeOut" }}
        />
      ))}
      {hearts.map((h) => (
        <motion.span
          key={`h${h.id}`}
          className="absolute left-1/2 bottom-6 text-pink-400"
          style={{ width: h.size, height: h.size }}
          initial={{ x: h.x, y: 0, opacity: 0 }}
          animate={{ y: -140, opacity: [0, 1, 0] }}
          transition={{ duration: 2.6, delay: h.delay, repeat: Infinity, repeatDelay: 1.2, ease: "easeOut" }}
        >
          <Heart className="h-full w-full" />
        </motion.span>
      ))}
      <motion.div
        className="relative flex h-24 w-24 items-center justify-center rounded-full bg-primary text-primary-foreground shadow-xl"
        initial={{ scale: 0, rotate: -30 }}
        animate={{ scale: [0, 1.25, 1], rotate: 0 }}
        transition={{ duration: 0.7, ease: "easeOut" }}
      >
        <motion.span animate={{ scale: [1, 1.15, 1] }} transition={{ duration: 1.1, repeat: Infinity, delay: 0.8 }}>
          <Heart className="h-11 w-11" />
        </motion.span>
      </motion.div>
    </div>
  );
}

/* ── Composant principal ────────────────────────────────────────────── */

export function MobileMoneyDonation({ className = "" }: { className?: string }) {
  const { data: cfg, isLoading, isError } = useQuery({ queryKey: ["donate-config"], queryFn: fetchDonateConfig, staleTime: 10 * 60_000 });

  const [amountText, setAmountText] = useState("1000");
  const [name, setName] = useState("");
  const [country, setCountry] = useState("");
  const [operator, setOperator] = useState("");
  const [phone, setPhone] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [current, setCurrent] = useState<{ id: string; url?: string } | null>(() => load());

  const amount = parseInt(amountText.replace(/\D/g, ""), 10) || 0;
  const countryObj = cfg?.countries.find((c) => c.code === country);

  useEffect(() => {
    if (cfg && !country) setCountry(cfg.countries.find((c) => c.code === "TG")?.code ?? cfg.countries[0]?.code ?? "");
  }, [cfg, country]);
  useEffect(() => {
    if (countryObj && !countryObj.operators.includes(operator)) setOperator(countryObj.operators[0] ?? "");
  }, [countryObj, operator]);

  // Suivi du don en cours (toutes les 3 s tant qu'il est en attente)
  const { data: status, isError: statusError } = useQuery({
    queryKey: ["donation-status", current?.id],
    queryFn: () => fetchDonationStatus(current!.id),
    enabled: !!current,
    refetchInterval: (q) => (q.state.data && q.state.data.status !== "awaiting_payment" ? false : 3000),
    retry: false,
  });
  useEffect(() => {
    if (statusError) {
      save(null);
      setCurrent(null);
    }
  }, [statusError]);

  const amountError =
    cfg && amount > 0 && (amount < cfg.min || amount > cfg.max)
      ? `Le don doit être entre ${fmt(cfg.min)} et ${fmt(cfg.max)} F`
      : null;
  const phoneDigits = phone.replace(/\D/g, "");
  const canSubmit = !!cfg && !busy && amount > 0 && !amountError && !!country && !!operator && phoneDigits.length >= 8;

  const submit = async () => {
    if (!canSubmit) return;
    setBusy(true);
    setError(null);
    // La fenêtre de paiement est ouverte tout de suite (sur le clic) pour ne pas être bloquée par le navigateur
    let win: Window | null = null;
    try {
      win = window.open("", "_blank");
    } catch {
      win = null;
    }
    try {
      const res = await createDonation({ amount, country, operator, phone: phoneDigits, donor_name: name.trim() || undefined });
      const next = { id: res.id, url: res.payment_url };
      save(next);
      setCurrent(next);
      if (win) win.location.href = res.payment_url;
      else window.open(res.payment_url, "_blank");
    } catch (e) {
      win?.close();
      setError(e instanceof Error ? e.message : "Impossible de lancer le paiement.");
    } finally {
      setBusy(false);
    }
  };

  const reset = () => {
    save(null);
    setCurrent(null);
    setError(null);
  };

  const state = !current ? "form" : status?.status === "paid" ? "paid" : status?.status === "failed" || status?.status === "expired" ? status.status : "waiting";

  return (
    <section className={`rounded-3xl border border-primary/40 bg-gradient-to-br from-primary/15 via-primary/5 to-transparent p-4 md:p-5 ${className}`}>
      <AnimatePresence mode="wait">
        {state === "form" && (
          <motion.div key="form" initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -8 }}>
            <div className="flex items-center gap-3">
              <span className="shrink-0 w-12 h-12 rounded-2xl bg-primary text-primary-foreground flex items-center justify-center">
                <Smartphone className="w-6 h-6" />
              </span>
              <div>
                <h2 className="font-display font-extrabold text-base leading-snug">Don par Mobile Money</h2>
                <p className="text-xs text-muted-foreground leading-snug">Tu paies exactement ce que tu choisis : aucun frais ajouté.</p>
              </div>
            </div>

            {isLoading && <p className="mt-4 text-sm text-muted-foreground inline-flex items-center gap-2"><Loader2 className="w-4 h-4 animate-spin" />Chargement…</p>}
            {isError && <p className="mt-4 text-sm text-destructive">Les dons par Mobile Money sont indisponibles pour le moment. Réessaie plus tard.</p>}

            {cfg && (
              <div className="mt-4 space-y-4">
                <div>
                  <label className="text-xs font-bold uppercase tracking-wide text-muted-foreground">Montant (F CFA)</label>
                  <div className="mt-2 grid grid-cols-4 gap-2">
                    {cfg.presets.map((p) => (
                      <button
                        key={p}
                        type="button"
                        onClick={() => setAmountText(String(p))}
                        className={`h-11 rounded-xl border text-sm font-bold transition-colors ${amount === p ? "bg-primary text-primary-foreground border-primary" : "bg-surface border-border-subtle hover:border-primary/60"}`}
                      >
                        {fmt(p)}
                      </button>
                    ))}
                  </div>
                  <input
                    inputMode="numeric"
                    value={amountText ? fmt(amount) : ""}
                    onChange={(e) => setAmountText(e.target.value)}
                    placeholder={`Autre montant (${fmt(cfg.min)} – ${fmt(cfg.max)})`}
                    className="mt-2 w-full h-12 rounded-xl bg-background border border-border px-3 text-base font-bold"
                  />
                  {amountError && <p className="mt-1 text-xs text-destructive">{amountError}</p>}
                </div>

                <div>
                  <label className="text-xs font-bold uppercase tracking-wide text-muted-foreground">Pseudo (facultatif)</label>
                  <input
                    value={name}
                    maxLength={40}
                    onChange={(e) => setName(e.target.value)}
                    placeholder="Comment veux-tu qu'on te remercie ?"
                    className="mt-2 w-full h-12 rounded-xl bg-background border border-border px-3 text-sm"
                  />
                </div>

                <div>
                  <label className="text-xs font-bold uppercase tracking-wide text-muted-foreground">Pays</label>
                  <select value={country} onChange={(e) => setCountry(e.target.value)} className="mt-2 w-full h-12 rounded-xl bg-background border border-border px-3 text-sm">
                    {cfg.countries.map((c) => (
                      <option key={c.code} value={c.code}>{c.name}</option>
                    ))}
                  </select>
                </div>

                {countryObj && (
                  <div>
                    <label className="text-xs font-bold uppercase tracking-wide text-muted-foreground">Moyen de paiement</label>
                    <div className="mt-2 flex flex-wrap gap-2">
                      {countryObj.operators.map((o) => (
                        <button
                          key={o}
                          type="button"
                          onClick={() => setOperator(o)}
                          className={`h-10 px-4 rounded-full border text-sm font-bold transition-colors ${operator === o ? "bg-primary text-primary-foreground border-primary" : "bg-surface border-border-subtle hover:border-primary/60"}`}
                        >
                          {o}
                        </button>
                      ))}
                    </div>
                  </div>
                )}

                <div>
                  <label className="text-xs font-bold uppercase tracking-wide text-muted-foreground">Ton numéro Mobile Money</label>
                  <input
                    type="tel"
                    inputMode="tel"
                    value={phone}
                    onChange={(e) => setPhone(e.target.value)}
                    placeholder="Ex. 90 12 34 56"
                    className="mt-2 w-full h-12 rounded-xl bg-background border border-border px-3 text-base"
                  />
                </div>

                {error && <p className="text-sm text-destructive">{error}</p>}

                <button
                  type="button"
                  disabled={!canSubmit}
                  onClick={() => void submit()}
                  className="w-full h-12 rounded-full bg-primary text-primary-foreground font-bold inline-flex items-center justify-center gap-2 disabled:opacity-50"
                >
                  {busy ? <Loader2 className="w-5 h-5 animate-spin" /> : <Heart className="w-5 h-5" />}
                  {amount > 0 ? `Donner ${fmt(amount)} F` : "Faire un don"}
                </button>
                <p className="flex gap-2 text-xs text-muted-foreground">
                  <ShieldCheck className="w-4 h-4 shrink-0 text-primary mt-0.5" />
                  Le paiement se valide sur une page sécurisée, puis sur ton téléphone. Nous ne gardons pas ton numéro au-delà du don.
                </p>
              </div>
            )}
          </motion.div>
        )}

        {state === "waiting" && (
          <motion.div key="waiting" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} className="text-center py-2">
            <WaitingAnimation />
            <h2 className="mt-2 font-display font-extrabold text-lg">En attente de ton paiement…</h2>
            <p className="mt-1 text-sm text-muted-foreground">
              Termine le paiement sur la page qui s'est ouverte, puis valide sur ton téléphone si on te le demande.
              Cette page se met à jour toute seule.
            </p>
            {current?.url && (
              <a href={current.url} target="_blank" rel="noopener noreferrer" className="mt-4 inline-flex items-center gap-2 h-11 px-5 rounded-full bg-primary text-primary-foreground text-sm font-bold">
                <ExternalLink className="w-4 h-4" /> Ouvrir la page de paiement
              </a>
            )}
            <div>
              <button type="button" onClick={reset} className="mt-3 text-xs text-muted-foreground underline">Annuler et recommencer</button>
            </div>
          </motion.div>
        )}

        {state === "paid" && (
          <motion.div key="paid" initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="text-center py-2">
            <SuccessAnimation />
            <h2 className="mt-1 font-display font-extrabold text-xl">Merci{status?.donor_name ? ` ${status.donor_name}` : ""} ! 💜</h2>
            <p className="mt-1 text-sm text-muted-foreground">
              Ton don de <b className="text-foreground">{fmt(status?.amount ?? amount)} F</b> est bien arrivé. Grâce à toi, Magi-Stream reste en ligne et gratuit pour tout le monde.
            </p>
            <button type="button" onClick={reset} className="mt-4 h-11 px-6 rounded-full bg-primary text-primary-foreground text-sm font-bold">
              Faire un autre don
            </button>
          </motion.div>
        )}

        {(state === "failed" || state === "expired") && (
          <motion.div key="failed" initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="text-center py-4">
            <h2 className="font-display font-extrabold text-lg">{state === "expired" ? "Le paiement a expiré" : "Le paiement n'a pas abouti"}</h2>
            <p className="mt-1 text-sm text-muted-foreground">Rien n'a été débité par nous. Tu peux réessayer quand tu veux.</p>
            <button type="button" onClick={reset} className="mt-4 h-11 px-6 rounded-full bg-primary text-primary-foreground text-sm font-bold">Réessayer</button>
          </motion.div>
        )}
      </AnimatePresence>
    </section>
  );
}
