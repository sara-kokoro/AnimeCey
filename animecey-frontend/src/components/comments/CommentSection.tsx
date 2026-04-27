import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { motion, AnimatePresence } from "framer-motion";
import { Heart, Send, Loader2 } from "lucide-react";
import { formatDistanceToNow } from "date-fns";
import { fr } from "date-fns/locale";
import { Link } from "react-router-dom";
import { Avatar } from "./Avatar";
import { fetchComments, createComment, likeComment, unlikeComment, type CommentData } from "@/api/comments";
import { useAuthStore } from "@/stores/auth";
import { cn } from "@/lib/utils";

function CommentItem({
  comment,
  onReply,
  isReply,
}: {
  comment: CommentData;
  onReply?: (parentId: number, content: string) => void;
  isReply?: boolean;
}) {
  const qc = useQueryClient();
  const [liked, setLiked] = useState(comment.is_liked_by_me);
  const [likesCount, setLikesCount] = useState(comment.likes_count);
  const [replyOpen, setReplyOpen] = useState(false);
  const [replyText, setReplyText] = useState("");

  const likeMutation = useMutation({
    mutationFn: () => liked ? unlikeComment(comment.id) : likeComment(comment.id),
    onSuccess: (data) => {
      setLiked(data.liked);
      setLikesCount(data.likes_count);
    },
  });

  return (
    <div className={cn("flex gap-3", isReply && "ml-8 pl-4 border-l-2 border-border-subtle")}>
      <Avatar name={comment.user.username} size={isReply ? 30 : 36} />
      <div className="flex-1 min-w-0">
        <div className="flex items-baseline gap-2 flex-wrap">
          <span className="font-body font-semibold text-sm text-foreground">
            {comment.user.username}
          </span>
          <span className="text-xs text-muted-foreground font-body">
            {formatDistanceToNow(new Date(comment.created_at), { addSuffix: true, locale: fr })}
          </span>
        </div>
        <p className="text-sm text-foreground font-body mt-1 leading-relaxed">{comment.content}</p>
        <div className="flex items-center gap-4 mt-2">
          <button
            onClick={() => likeMutation.mutate()}
            className="inline-flex items-center gap-1.5 text-xs text-muted-foreground hover:text-foreground transition-colors"
          >
            <motion.span key={String(liked)} initial={{ scale: 0.6 }} animate={{ scale: 1 }} transition={{ type: "spring", stiffness: 400, damping: 14 }}>
              <Heart className={cn("w-3.5 h-3.5", liked && "fill-primary text-primary")} />
            </motion.span>
            {likesCount}
          </button>
          {!isReply && onReply && (
            <button
              onClick={() => setReplyOpen((v) => !v)}
              className="text-xs font-body font-semibold text-muted-foreground hover:text-foreground transition-colors"
            >
              Répondre
            </button>
          )}
        </div>

        <AnimatePresence>
          {replyOpen && (
            <motion.div
              initial={{ opacity: 0, height: 0 }}
              animate={{ opacity: 1, height: "auto" }}
              exit={{ opacity: 0, height: 0 }}
              className="mt-3 overflow-hidden"
            >
              <div className="flex gap-2">
                <input
                  value={replyText}
                  onChange={(e) => setReplyText(e.target.value)}
                  placeholder="Écris une réponse..."
                  className="flex-1 bg-surface-2 border border-border rounded-lg px-3 py-2 text-sm font-body focus:outline-none focus:border-primary transition-colors"
                />
                <button
                  disabled={!replyText.trim()}
                  onClick={() => {
                    if (onReply && replyText.trim()) {
                      onReply(comment.id, replyText);
                      setReplyText("");
                      setReplyOpen(false);
                    }
                  }}
                  className="px-3 py-2 rounded-lg bg-primary text-primary-foreground text-sm font-body font-semibold disabled:opacity-40 disabled:cursor-not-allowed"
                >
                  <Send className="w-4 h-4" />
                </button>
              </div>
            </motion.div>
          )}
        </AnimatePresence>

        {comment.replies && comment.replies.length > 0 && (
          <div className="mt-3 space-y-3">
            {comment.replies.map((r) => (
              <CommentItem key={r.id} comment={r} isReply />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

export function CommentSection({ episodeId }: { episodeId: number }) {
  const qc = useQueryClient();
  const { isAuthenticated } = useAuthStore();
  const [text, setText] = useState("");
  const [page, setPage] = useState(1);
  const max = 500;

  const { data, isLoading } = useQuery({
    queryKey: ["comments", episodeId, page],
    queryFn: () => fetchComments(episodeId, page, 20),
  });

  const comments = data?.items ?? [];

  const submitMutation = useMutation({
    mutationFn: (payload: { episode_id: number; content: string; parent_id?: number }) => createComment(payload),
    onSuccess: () => {
      setText("");
      qc.invalidateQueries({ queryKey: ["comments", episodeId] });
    },
  });

  const submit = () => {
    const t = text.trim();
    if (!t || !isAuthenticated) return;
    submitMutation.mutate({ episode_id: episodeId, content: t });
  };

  const onReply = (parentId: number, content: string) => {
    if (!isAuthenticated) return;
    submitMutation.mutate({ episode_id: episodeId, content, parent_id: parentId });
  };

  return (
    <div>
      <h3 className="font-display font-bold text-lg mb-4">
        Commentaires {data?.total ? `(${data.total})` : ""}
      </h3>

      {isAuthenticated ? (
        <div className="mb-6">
          <div className="relative">
            <textarea
              value={text}
              onChange={(e) => setText(e.target.value.slice(0, max))}
              placeholder="Partage ton avis..."
              rows={3}
              className="w-full bg-surface border border-border rounded-xl px-4 py-3 text-sm font-body focus:outline-none focus:border-primary transition-colors resize-none"
            />
            <span className="absolute bottom-3 right-3 text-[10px] text-muted-foreground/60 font-body">
              {text.length}/{max}
            </span>
          </div>
          <div className="flex justify-end mt-2">
            <button
              onClick={submit}
              disabled={!text.trim() || submitMutation.isPending}
              className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-primary text-primary-foreground text-sm font-body font-semibold disabled:opacity-40"
            >
              {submitMutation.isPending ? <Loader2 className="w-4 h-4 animate-spin" /> : <Send className="w-4 h-4" />}
              Publier
            </button>
          </div>
        </div>
      ) : (
        <div className="mb-6 bg-surface border border-border rounded-xl p-4 text-center">
          <p className="text-sm text-muted-foreground font-body">
            <Link to="/auth" className="text-primary font-semibold hover:underline">Connecte-toi</Link>
            {" "}pour commenter.
          </p>
        </div>
      )}

      {isLoading ? (
        <div className="flex justify-center py-8"><Loader2 className="w-6 h-6 animate-spin text-primary" /></div>
      ) : comments.length === 0 ? (
        <p className="text-center text-muted-foreground font-body py-8">Aucun commentaire. Sois le premier !</p>
      ) : (
        <div className="space-y-5">
          {comments.map((c) => (
            <CommentItem key={c.id} comment={c} onReply={onReply} />
          ))}
          {(data?.pages ?? 1) > 1 && (
            <div className="flex justify-center gap-2 pt-4">
              <button disabled={page <= 1} onClick={() => setPage((p) => p - 1)} className="px-3 py-1.5 rounded-lg text-xs font-body font-semibold bg-surface border border-border disabled:opacity-40">Précédent</button>
              <button disabled={page >= (data?.pages ?? 1)} onClick={() => setPage((p) => p + 1)} className="px-3 py-1.5 rounded-lg text-xs font-body font-semibold bg-surface border border-border disabled:opacity-40">Suivant</button>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
