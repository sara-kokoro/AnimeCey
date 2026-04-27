import { motion } from "framer-motion";
import { Link } from "react-router-dom";
import { Info, Sparkles, AlertTriangle, Wrench } from "lucide-react";
import { formatDistanceToNow } from "date-fns";
import { fr } from "date-fns/locale";
import { useNotificationStore } from "@/stores/notifications";
import { cn } from "@/lib/utils";

const typeIcon = {
  info: Info,
  new: Sparkles,
  alert: AlertTriangle,
  maintenance: Wrench,
};

const typeColor = {
  info: "text-info",
  new: "text-primary",
  alert: "text-destructive",
  maintenance: "text-warning",
};

export function NotificationDropdown({ onClose }: { onClose: () => void }) {
  const { notifications, markAllAsRead } = useNotificationStore();
  const top = notifications.slice(0, 5);

  return (
    <motion.div
      initial={{ opacity: 0, y: -10 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -10 }}
      transition={{ duration: 0.18 }}
      className="absolute right-0 mt-2 w-[360px] max-w-[90vw] bg-surface border border-border rounded-xl shadow-2xl overflow-hidden z-50"
    >
      <div className="px-4 py-3 flex items-center justify-between border-b border-border">
        <h3 className="font-display font-bold text-base">Notifications</h3>
        <button
          onClick={markAllAsRead}
          className="text-xs font-body font-semibold text-primary hover:text-primary-dim transition-colors"
        >
          Tout lire
        </button>
      </div>
      <div className="max-h-[400px] overflow-y-auto">
        {top.length === 0 && (
          <p className="px-4 py-8 text-sm text-muted-foreground text-center font-body">
            Aucune notification
          </p>
        )}
        {top.map((n) => {
          const Icon = typeIcon[n.type];
          return (
            <Link
              key={n.id}
              to={`/notifications#${n.id}`}
              onClick={onClose}
              className={cn(
                "block px-4 py-3 border-b border-border-subtle hover:bg-surface-2 transition-colors",
                !n.is_read && "bg-surface-2/50",
              )}
            >
              <div className="flex gap-3">
                <Icon className={cn("w-4 h-4 mt-0.5 shrink-0", typeColor[n.type])} />
                <div className="min-w-0 flex-1">
                  <p className="font-body font-semibold text-sm text-foreground truncate">
                    {n.title}
                  </p>
                  <p className="text-xs text-muted-foreground font-body line-clamp-2 mt-0.5">
                    {n.content}
                  </p>
                  <p className="text-[11px] text-muted-foreground/70 font-body mt-1">
                    {formatDistanceToNow(new Date(n.created_at), { addSuffix: true, locale: fr })}
                  </p>
                </div>
                {!n.is_read && <span className="w-2 h-2 rounded-full bg-primary mt-2 shrink-0" />}
              </div>
            </Link>
          );
        })}
      </div>
      <Link
        to="/notifications"
        onClick={onClose}
        className="block px-4 py-3 text-center text-sm font-body font-semibold text-primary hover:bg-surface-2 transition-colors border-t border-border"
      >
        Voir toutes les notifications
      </Link>
    </motion.div>
  );
}