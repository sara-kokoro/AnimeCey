import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Heart, Send } from "lucide-react";
import { formatDistanceToNow } from "date-fns";
import { fr } from "date-fns/locale";
import { Link } from "react-router-dom";
import { Avatar } from "./Avatar";
import { getComments, type MockComment } from "@/data/mock";
import { cn } from "@/lib/utils";

function CommentItem({
  comment,
  onReply,
  isReply,
}: {
  comment: MockComment;
  onReply?: (parentId: number, content: string) => void;
  isReply?: boolean;
}) {
  const [liked, setLiked] = useState(comment.is_liked_by_me);
  const [replyOpen, setReplyOpen] = useState(false);
  const [replyText, setReplyText] = useState("");

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
            onClick={() => setLiked((v) => !v)}
            className="inline-flex items-center gap-1.5 text-xs text-muted-foreground hover:text-foreground transition-colors"
          >
            <motion.span key={String(liked)} initial={{ scale: 0.6 }} animate={{ scale: 1 }} transition={{ type: "spring", stiffness: 400, damping: 14 }}>
              <Heart className={cn("w-3.5 h-3.5", liked && "fill-primary text-primary")} />
            </motion.span>
            {comment.likes_count + (liked ? 1 : 0)}
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
  const [comments, setComments] = useState<MockComment[]>(() => getComments(episodeId));
  const [text, setText] = useState("");
  const max = 500;

  const submit = () => {
    const t = text.trim();
    if (!t) return;
    const c: MockComment = {
      id: Date.now(),
      episode_id: episodeId,
      user: { id: 0, username: "Toi" },
      content: t,
      likes_count: 0,
      is_liked_by_me: false,
      created_at: new Date().toISOString(),
      replies: [],
    };
    setComments((cs) => [c, ...cs]);
    setText("");
  };

  const onReply = (parentId: number, content: string) => {
    setComments((cs) =>
      cs.map((c) =>
        c.id === parentId
          ? {
              ...c,
              replies: [
                ...(c.replies ?? []),
                {
                  id: Date.now(),
                  episode_id: episodeId,
                  user: { id: 0, username: "Toi" },
                  content,
                  likes_count: 0,
                  is_liked_by_me: false,
                  parent_id: parentId,
                  created_at: new Date().toISOString(),
                },
              ],
            }
          : c,
      ),
    );
  };

  return (
    <section id="comments" className="px-4 md:px-0 mt-10">
      <h2 className="font-display font-bold text-xl mb-4">
        Commentaires <span className="text-muted-foreground font-normal">({comments.length})</span>
      </h2>

      {/* Connected form (mock) */}
      <div className="bg-surface border border-border rounded-xl p-4 mb-6">
        <div className="flex gap-3">
          <Avatar name="Toi" />
          <div className="flex-1 min-w-0">
            <textarea
              value={text}
              onChange={(e) => setText(e.target.value.slice(0, max))}
              placeholder="Écris un commentaire..."
              rows={3}
              className="w-full bg-surface-2 border border-border rounded-lg px-3 py-2 text-sm font-body resize-none focus:outline-none focus:border-primary transition-colors"
            />
            <div className="flex items-center justify-between mt-2">
              <span
                className={cn(
                  "text-xs font-body",
                  text.length > max * 0.9 ? "text-destructive" : "text-muted-foreground",
                )}
              >
                {text.length} / {max}
              </span>
              <button
                disabled={!text.trim()}
                onClick={submit}
                className="px-4 py-2 rounded-lg bg-primary text-primary-foreground text-sm font-body font-semibold disabled:opacity-40 disabled:cursor-not-allowed hover:bg-primary-dim transition-colors"
              >
                Publier
              </button>
            </div>
          </div>
        </div>
      </div>

      {/* Auth banner (UI only) */}
      <Link
        to="/auth"
        className="block mb-6 p-3 rounded-lg border border-border-subtle bg-surface-2/50 text-sm font-body text-muted-foreground hover:border-primary/40 transition-colors text-center"
      >
        Connecte-toi pour commenter avec ton pseudo
      </Link>

      <div className="space-y-6">
        <AnimatePresence initial={false}>
          {comments.map((c) => (
            <motion.div
              key={c.id}
              initial={{ opacity: 0, y: -8, backgroundColor: "hsl(var(--primary) / 0.05)" }}
              animate={{ opacity: 1, y: 0, backgroundColor: "hsl(var(--primary) / 0)" }}
              transition={{ duration: 0.4 }}
              className="rounded-lg"
            >
              <CommentItem comment={c} onReply={onReply} />
            </motion.div>
          ))}
        </AnimatePresence>
      </div>
    </section>
  );
}