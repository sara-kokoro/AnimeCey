import { useEffect, useState } from "react";
import { useNavigate } from "@/lib/router";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Check, Download, Loader2 } from "lucide-react";
import { toast } from "sonner";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { useAuthStore } from "@/stores/auth";
import { downloadFileUrl, fetchDownloadInfo, requestDownloadTicket } from "@/api/episodes";

type Phase = "idle" | "waiting" | "ready";

function errorMessage(err: unknown): string {
  const detail = (err as { response?: { data?: { detail?: unknown } } })?.response?.data?.detail;
  return typeof detail === "string" ? detail : "Impossible de lancer le téléchargement. Réessaie dans un instant.";
}

/**
 * Bouton « Télécharger » : visible seulement si le titre est téléchargeable (commande /dl du bot).
 * Parcours : compte obligatoire -> pub (SmartLink dans un nouvel onglet) -> compte à rebours -> fichier.
 */
export function DownloadButton({ episodeId }: { episodeId: number }) {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const isAuthenticated = useAuthStore((s) => s.isAuthenticated);

  const [open, setOpen] = useState(false);
  const [phase, setPhase] = useState<Phase>("idle");
  const [ticket, setTicket] = useState<string | null>(null);
  const [seconds, setSeconds] = useState(0);

  const infoKey = ["download-info", episodeId, isAuthenticated];
  const { data: info } = useQuery({
    queryKey: infoKey,
    queryFn: () => fetchDownloadInfo(episodeId),
    staleTime: 60_000,
  });

  // Compte à rebours pendant que la pub est affichée
  useEffect(() => {
    if (phase !== "waiting" || !ticket) return; // le décompte commence quand le ticket est arrivé
    if (seconds <= 0) {
      setPhase("ready");
      return;
    }
    const t = setTimeout(() => setSeconds((n) => n - 1), 1000);
    return () => clearTimeout(t);
  }, [phase, seconds, ticket]);

  // Changement d'épisode : on repart de zéro
  useEffect(() => {
    setOpen(false);
    setPhase("idle");
    setTicket(null);
  }, [episodeId]);

  if (!info?.downloadable) return null;

  const onOpen = () => {
    if (!isAuthenticated) {
      toast.info("Connecte-toi pour télécharger cet épisode.");
      navigate("/auth");
      return;
    }
    setPhase("idle");
    setTicket(null);
    setOpen(true);
  };

  const onContinue = async () => {
    setPhase("waiting");
    try {
      const res = await requestDownloadTicket(episodeId);
      setTicket(res.ticket);
      setSeconds(res.wait_seconds);
    } catch (err) {
      const status = (err as { response?: { status?: number } })?.response?.status;
      setPhase("idle");
      if (status === 401) {
        setOpen(false);
        navigate("/auth");
        return;
      }
      toast.error(errorMessage(err));
    }
  };

  const onFileClick = () => {
    // Le téléchargement démarre dans le navigateur ; on referme et on met le compteur à jour.
    setTimeout(() => {
      setOpen(false);
      setPhase("idle");
      setTicket(null);
      queryClient.invalidateQueries({ queryKey: ["download-info", episodeId] });
    }, 1500);
  };

  const remaining = info.remaining;

  return (
    <>
      <button
        onClick={onOpen}
        className="inline-flex items-center gap-1.5 px-3 py-2 rounded-lg bg-surface border border-border text-sm font-body font-semibold hover:border-primary/40 transition-colors"
      >
        <Download className="w-4 h-4" />
        Télécharger
      </button>

      <Dialog open={open} onOpenChange={(v) => phase !== "waiting" && setOpen(v)}>
        <DialogContent className="max-w-sm">
          <DialogHeader>
            <DialogTitle className="font-display">Télécharger l'épisode</DialogTitle>
            <DialogDescription className="font-body">
              {phase === "idle" && "Le téléchargement démarre après un court décompte. Merci de soutenir le site !"}
              {phase === "waiting" && "Ton téléchargement va démarrer. Laisse cette page ouverte."}
              {phase === "ready" && "C'est prêt !"}
            </DialogDescription>
          </DialogHeader>

          {phase === "idle" && (
            <div className="space-y-3">
              {remaining !== null && (
                <p className="text-xs text-muted-foreground font-body">
                  {remaining > 0
                    ? `Il te reste ${remaining} téléchargement${remaining > 1 ? "s" : ""} sur ${info.daily_limit} pour les prochaines 24 h.`
                    : `Limite atteinte : ${info.daily_limit} téléchargements par 24 h.`}
                </p>
              )}
              <button
                onClick={onContinue}
                disabled={remaining === 0}
                className="w-full inline-flex items-center justify-center gap-2 px-4 py-2.5 rounded-lg bg-primary text-primary-foreground font-body font-bold disabled:opacity-40 disabled:cursor-not-allowed"
              >
                <Download className="w-4 h-4" />
                Continuer
              </button>
            </div>
          )}

          {phase === "waiting" && (
            <div className="flex flex-col items-center gap-2 py-3">
              <Loader2 className="w-8 h-8 text-primary animate-spin" />
              <p className="font-body text-sm text-muted-foreground">
                {ticket ? `Téléchargement disponible dans ${seconds} s…` : "Préparation…"}
              </p>
            </div>
          )}

          {phase === "ready" && ticket && (
            <a
              href={downloadFileUrl(episodeId, ticket)}
              download
              onClick={onFileClick}
              className="w-full inline-flex items-center justify-center gap-2 px-4 py-2.5 rounded-lg bg-primary text-primary-foreground font-body font-bold"
            >
              <Check className="w-4 h-4" />
              Télécharger le fichier
            </a>
          )}
        </DialogContent>
      </Dialog>
    </>
  );
}
