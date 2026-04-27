import { motion } from "framer-motion";
import { useState } from "react";
import { Info, Sparkles, AlertTriangle, Wrench, X } from "lucide-react";
import { formatDistanceToNow } from "date-fns";
import { fr } from "date-fns/locale";
import { Navbar } from "@/components/layout/Navbar";
import { Footer } from "@/components/layout/Footer";
import { useNotificationStore } from "@/stores/notifications";
import type { MockNotification } from "@/data/mock";
import { cn } from "@/lib/utils";

const typeIcon = { info: Info, new: Sparkles, alert: AlertTriangle, maintenance: Wrench };
const typeColor = {
  info: "text-info",
  new: "text-primary",
  alert: "text-destructive",
  maintenance: "text-warning",
};
const typeLabel = { info: "Info", new: "Nouveauté", alert: "Alerte", maintenance: "Maintenance" };

export default function Notifications() {
  const { notifications, markAllAsRead, markAsRead } = useNotificationStore();
  const [open, setOpen] = useState<MockNotification | null>(null);

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.35 }}
      className="min-h-screen bg-background"
    >
      <Navbar />
      <main className="pt-24 mx-auto max-w-3xl px-4 md:px-6 pb-20">
        <div className="flex items-center justify-between mb-6">
          <div>
            <h1 className="font-display font-extrabold text-3xl">Notifications</h1>
            <p className="text-sm text-muted-foreground font-body mt-1">
              Toutes les annonces de l'équipe AnimeCey.
            </p>
          </div>
          <button
            onClick={markAllAsRead}
            className="text-sm font-body font-semibold text-primary hover:text-primary-dim transition-colors"
          >
            Tout marquer comme lu
          </button>
        </div>

        <div className="space-y-2">
          {notifications.map((n) => {
            const Icon = typeIcon[n.type];
            return (
              <button
                key={n.id}
                onClick={() => {
                  setOpen(n);
                  if (!n.is_read) markAsRead(n.id);
                }}
                className={cn(
                  "w-full text-left p-4 rounded-xl border border-border bg-surface hover:border-primary/40 transition-all",
                  !n.is_read && "bg-surface-2",
                )}
              >
                <div className="flex gap-3">
                  <Icon className={cn("w-5 h-5 mt-0.5 shrink-0", typeColor[n.type])} />
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2 flex-wrap">
                      <h3 className="font-display font-semibold">{n.title}</h3>
                      <span className="text-[10px] uppercase tracking-wider font-body font-bold text-muted-foreground">
                        {typeLabel[n.type]}
                      </span>
                    </div>
                    <p className="text-sm text-muted-foreground font-body mt-1 line-clamp-2">
                      {n.content}
                    </p>
                    <p className="text-xs text-muted-foreground/70 font-body mt-1.5">
                      {formatDistanceToNow(new Date(n.created_at), { addSuffix: true, locale: fr })}
                    </p>
                  </div>
                  {!n.is_read && <span className="w-2 h-2 rounded-full bg-primary mt-2 shrink-0" />}
                </div>
              </button>
            );
          })}
        </div>
      </main>

      {open && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          className="fixed inset-0 z-[70] bg-background/80 backdrop-blur-md flex items-center justify-center p-4"
          onClick={() => setOpen(null)}
        >
          <motion.div
            initial={{ scale: 0.95, opacity: 0 }}
            animate={{ scale: 1, opacity: 1 }}
            onClick={(e) => e.stopPropagation()}
            className="bg-surface border border-border rounded-2xl max-w-lg w-full p-6 relative"
          >
            <button
              onClick={() => setOpen(null)}
              aria-label="Fermer"
              className="absolute top-4 right-4 w-8 h-8 rounded-full flex items-center justify-center hover:bg-surface-2 transition-colors"
            >
              <X className="w-4 h-4" />
            </button>
            <span className="text-[10px] uppercase tracking-wider font-body font-bold text-primary">
              {typeLabel[open.type]}
            </span>
            <h2 className="font-display font-bold text-2xl mt-1">{open.title}</h2>
            {open.image_url && (
              <div className="mt-4 rounded-lg overflow-hidden">
                <img src={open.image_url} alt="" className="w-full h-auto" />
              </div>
            )}
            {open.caption && (
              <p className="italic text-sm text-muted-foreground font-body mt-2">{open.caption}</p>
            )}
            <p className="text-foreground font-body mt-4 leading-relaxed">{open.content}</p>
          </motion.div>
        </motion.div>
      )}

      <Footer />
    </motion.div>
  );
}