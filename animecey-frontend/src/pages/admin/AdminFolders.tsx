import { useState } from "react";
import { ChevronRight, FolderOpen, Folder, FileVideo, Copy, Trash2, Plus } from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";
import { mockFolders, type MockFolder } from "@/data/mock";
import { toast } from "sonner";
import { cn } from "@/lib/utils";

function FolderNode({ folder, depth = 0 }: { folder: MockFolder; depth?: number }) {
  const [open, setOpen] = useState(depth < 1);
  const Icon = folder.type === "anime" ? FolderOpen : folder.type === "language" ? Folder : FileVideo;

  const copyId = () => {
    navigator.clipboard.writeText(`/upload ${folder.id}`);
    toast.success("Commande copiée !");
  };

  return (
    <div className={cn(depth > 0 && "ml-6 border-l border-border-subtle pl-3")}>
      <div className="flex items-center gap-2 py-2 group">
        {folder.children && folder.children.length > 0 ? (
          <button onClick={() => setOpen((v) => !v)} aria-label="Ouvrir" className="text-muted-foreground hover:text-foreground">
            <ChevronRight className={cn("w-4 h-4 transition-transform", open && "rotate-90")} />
          </button>
        ) : (
          <span className="w-4" />
        )}
        <Icon className={cn("w-4 h-4", folder.type === "anime" ? "text-primary" : "text-muted-foreground")} />
        <span className="font-body font-semibold text-sm">{folder.name}</span>
        <span className="text-[10px] uppercase font-body font-bold text-primary bg-primary/10 px-1.5 py-0.5 rounded">
          {folder.episodes_count} ép.
        </span>
        <div className="ml-auto flex gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
          {folder.type === "season" && (
            <button onClick={copyId} className="inline-flex items-center gap-1 text-xs px-2 py-1 rounded-md bg-surface border border-border hover:border-primary/40 transition-colors">
              <Copy className="w-3 h-3" />
              Copier ID
            </button>
          )}
          {folder.type !== "season" && (
            <button className="inline-flex items-center gap-1 text-xs px-2 py-1 rounded-md bg-surface border border-border hover:border-primary/40 transition-colors">
              <Plus className="w-3 h-3" />
              {folder.type === "anime" ? "Langue" : "Saison"}
            </button>
          )}
          <button aria-label="Supprimer" className="w-7 h-7 rounded-md hover:bg-destructive/10 text-destructive flex items-center justify-center">
            <Trash2 className="w-3.5 h-3.5" />
          </button>
        </div>
      </div>
      <AnimatePresence initial={false}>
        {open && folder.children && (
          <motion.div initial={{ height: 0, opacity: 0 }} animate={{ height: "auto", opacity: 1 }} exit={{ height: 0, opacity: 0 }} className="overflow-hidden">
            {folder.children.map((c) => (
              <FolderNode key={c.id} folder={c} depth={depth + 1} />
            ))}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

export default function AdminFolders() {
  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="font-display font-extrabold text-3xl mb-1">Dossiers</h1>
          <p className="text-muted-foreground font-body">Arborescence des animés, langues et saisons.</p>
        </div>
        <button className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-primary text-primary-foreground text-sm font-body font-semibold">
          <Plus className="w-4 h-4" />
          Nouveau dossier
        </button>
      </div>

      <div className="bg-surface border border-border rounded-xl p-4">
        {mockFolders.map((f) => (
          <FolderNode key={f.id} folder={f} />
        ))}
      </div>
    </div>
  );
}