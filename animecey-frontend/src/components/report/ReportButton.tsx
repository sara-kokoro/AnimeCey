import { useState } from "react";
import { Flag, Loader2 } from "lucide-react";
import { toast } from "sonner";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { sendReport, type ReportKind } from "@/api/reports";
import { cn } from "@/lib/utils";

type Option = { value: ReportKind; label: string; hint?: string };

// Problèmes proposés sur la page d'un épisode
const EPISODE_KINDS: Option[] = [
  { value: "not_playable", label: "La vidéo ne se lance pas ou saccade" },
  { value: "wrong_language", label: "Mauvaise langue ou audio" },
  { value: "subtitles", label: "Sous-titres absents ou décalés" },
  { value: "wrong_content", label: "Ce n'est pas le bon épisode" },
  { value: "quality", label: "Image ou son de mauvaise qualité" },
  { value: "other", label: "Autre problème" },
];

// Problèmes proposés sur la page d'un film, d'une série ou d'un animé
const TITLE_KINDS: Option[] = [
  { value: "missing_episode", label: "Épisode(s) ou saison manquant(s)", hint: "Dis lesquels dans le message." },
  { value: "not_playable", label: "Des épisodes ne se lisent pas", hint: "Précise le numéro des épisodes." },
  { value: "wrong_language", label: "Langue manquante (VF ou VOSTFR)" },
  { value: "wrong_info", label: "Infos erronées (titre, synopsis, affiche)" },
  { value: "other", label: "Autre problème" },
];

interface Props {
  animeId?: number;
  /** Si fourni, le signalement concerne cet épisode précis. */
  episodeId?: number;
  label?: string;
  className?: string;
}

export function ReportButton({ animeId, episodeId, label = "Signaler un problème", className }: Props) {
  const options = episodeId ? EPISODE_KINDS : TITLE_KINDS;
  const [open, setOpen] = useState(false);
  const [kind, setKind] = useState<ReportKind | null>(null);
  const [message, setMessage] = useState("");
  const [contact, setContact] = useState("");
  const [website, setWebsite] = useState(""); // champ piège
  const [sending, setSending] = useState(false);

  const needsMessage = kind === "missing_episode" || kind === "other";
  const messageTooShort = needsMessage && message.trim().length < 3;
  const canSend = !!kind && !messageTooShort && !sending;
  const selected = options.find((o) => o.value === kind);

  const reset = () => {
    setKind(null);
    setMessage("");
    setContact("");
    setWebsite("");
  };

  const submit = async () => {
    if (!kind || !canSend) return;
    setSending(true);
    try {
      await sendReport({
        kind,
        anime_id: animeId,
        episode_id: episodeId,
        message: message.trim() || undefined,
        contact: contact.trim() || undefined,
        page_url: window.location.href.slice(0, 300),
        website,
      });
      toast.success("Merci ! Ton signalement a bien été envoyé.");
      setOpen(false);
      reset();
    } catch (err: unknown) {
      const detail = (err as { response?: { data?: { detail?: unknown } } })?.response?.data?.detail;
      toast.error(typeof detail === "string" ? detail : "Impossible d'envoyer le signalement. Réessaie dans un instant.");
    } finally {
      setSending(false);
    }
  };

  return (
    <>
      <button
        type="button"
        onClick={() => setOpen(true)}
        className={cn(
          "inline-flex items-center gap-2 px-3 py-2 rounded-lg bg-surface border border-border text-sm font-body font-semibold text-foreground hover:border-primary/40 transition-colors",
          className,
        )}
      >
        <Flag className="w-4 h-4" />
        {label}
      </button>

      <Dialog
        open={open}
        onOpenChange={(v) => {
          setOpen(v);
          if (!v) reset();
        }}
      >
        <DialogContent className="max-w-md max-h-[90vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle className="font-display">Signaler un problème</DialogTitle>
            <DialogDescription className="font-body">
              {episodeId ? "Que se passe-t-il avec cet épisode ?" : "Que se passe-t-il avec ce titre ?"} Pas besoin de compte.
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-2" role="radiogroup" aria-label="Type de problème">
            {options.map((o) => (
              <button
                key={o.value}
                type="button"
                role="radio"
                aria-checked={kind === o.value}
                onClick={() => setKind(o.value)}
                className={cn(
                  "w-full text-left px-3.5 py-2.5 rounded-lg border text-sm font-body transition-colors",
                  kind === o.value
                    ? "border-primary bg-primary/10 text-foreground"
                    : "border-border bg-surface text-foreground/90 hover:border-primary/40",
                )}
              >
                {o.label}
              </button>
            ))}
          </div>

          {kind && (
            <div className="space-y-3">
              <div>
                <label className="block text-xs font-body font-semibold text-muted-foreground mb-1.5">
                  {needsMessage ? "Décris le problème" : "Détails (facultatif)"}
                </label>
                <textarea
                  value={message}
                  onChange={(e) => setMessage(e.target.value)}
                  maxLength={1000}
                  rows={3}
                  placeholder={selected?.hint ?? "Quelques mots suffisent."}
                  className="w-full rounded-lg bg-surface border border-border px-3 py-2 text-sm font-body focus:outline-none focus:border-primary/60"
                />
              </div>
              <div>
                <label className="block text-xs font-body font-semibold text-muted-foreground mb-1.5">
                  Pour te répondre (facultatif) : e-mail ou @Telegram
                </label>
                <input
                  type="text"
                  value={contact}
                  onChange={(e) => setContact(e.target.value)}
                  maxLength={120}
                  className="w-full rounded-lg bg-surface border border-border px-3 py-2 text-sm font-body focus:outline-none focus:border-primary/60"
                />
              </div>
              {/* Champ piège : invisible pour un humain, rempli par certains robots */}
              <input
                type="text"
                name="website"
                tabIndex={-1}
                autoComplete="off"
                aria-hidden="true"
                value={website}
                onChange={(e) => setWebsite(e.target.value)}
                className="absolute left-[-9999px] h-0 w-0 opacity-0"
              />
            </div>
          )}

          <button
            type="button"
            onClick={submit}
            disabled={!canSend}
            className="w-full inline-flex items-center justify-center gap-2 px-4 py-2.5 rounded-lg bg-primary text-primary-foreground font-body font-semibold disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {sending && <Loader2 className="w-4 h-4 animate-spin" />}
            Envoyer le signalement
          </button>
        </DialogContent>
      </Dialog>
    </>
  );
}
