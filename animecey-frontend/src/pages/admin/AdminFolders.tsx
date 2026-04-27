import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { ChevronRight, FolderOpen, Folder, FileVideo, Copy, Trash2, Plus, Loader2 } from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";
import { adminListFolders, adminCreateFolder, adminDeleteFolder, adminListAnimes } from "@/api/admin";
import { getApiError } from "@/api/axios";
import { toast } from "sonner";
import { cn } from "@/lib/utils";

interface FolderItem {
  id: number;
  anime_id?: number;
  name: string;
  folder_type: string;
  language?: string;
  season_number?: number;
  parent_id?: number;
  children?: FolderItem[];
  created_at?: string;
}

function FolderNode({ folder, depth = 0, onDelete, onAddChild }: {
  folder: FolderItem;
  depth?: number;
  onDelete: (id: number) => void;
  onAddChild: (parentId: number, animeId: number | undefined, folderType: string) => void;
}) {
  const [open, setOpen] = useState(depth < 1);
  const hasChildren = folder.children && folder.children.length > 0;
  const Icon = folder.folder_type === "anime" ? FolderOpen : folder.folder_type === "language" ? Folder : FileVideo;

  const copyId = () => {
    navigator.clipboard.writeText(`/upload ${folder.id}`);
    toast.success("Commande copiée !");
  };

  return (
    <div className={cn(depth > 0 && "ml-6 border-l border-border-subtle pl-3")}>
      <div className="flex items-center gap-2 py-2 group">
        {hasChildren ? (
          <button onClick={() => setOpen((v) => !v)} aria-label="Ouvrir" className="text-muted-foreground hover:text-foreground">
            <ChevronRight className={cn("w-4 h-4 transition-transform", open && "rotate-90")} />
          </button>
        ) : (
          <span className="w-4" />
        )}
        <Icon className={cn("w-4 h-4", folder.folder_type === "anime" ? "text-primary" : "text-muted-foreground")} />
        <span className="font-body font-semibold text-sm">{folder.name}</span>
        {folder.language && (
          <span className="text-[10px] uppercase font-body font-bold text-primary bg-primary/10 px-1.5 py-0.5 rounded">
            {folder.language}
          </span>
        )}
        {folder.season_number != null && (
          <span className="text-[10px] font-body text-muted-foreground">
            S{folder.season_number}
          </span>
        )}
        <span className="text-[10px] font-body text-muted-foreground">
          ID: {folder.id}
        </span>
        <div className="ml-auto flex gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
          {(folder.folder_type === "season" || folder.folder_type === "language") && (
            <button onClick={copyId} className="inline-flex items-center gap-1 text-xs px-2 py-1 rounded-md bg-surface border border-border hover:border-primary/40 transition-colors">
              <Copy className="w-3 h-3" />
              Copier ID
            </button>
          )}
          {folder.folder_type === "anime" && (
            <button
              onClick={() => onAddChild(folder.id, folder.anime_id, "language")}
              className="inline-flex items-center gap-1 text-xs px-2 py-1 rounded-md bg-surface border border-border hover:border-primary/40 transition-colors"
            >
              <Plus className="w-3 h-3" />
              Langue
            </button>
          )}
          {folder.folder_type === "language" && (
            <button
              onClick={() => onAddChild(folder.id, folder.anime_id, "season")}
              className="inline-flex items-center gap-1 text-xs px-2 py-1 rounded-md bg-surface border border-border hover:border-primary/40 transition-colors"
            >
              <Plus className="w-3 h-3" />
              Saison
            </button>
          )}
          <button
            onClick={() => onDelete(folder.id)}
            aria-label="Supprimer"
            className="w-7 h-7 rounded-md hover:bg-destructive/10 text-destructive flex items-center justify-center"
          >
            <Trash2 className="w-3.5 h-3.5" />
          </button>
        </div>
      </div>
      <AnimatePresence initial={false}>
        {open && hasChildren && (
          <motion.div initial={{ height: 0, opacity: 0 }} animate={{ height: "auto", opacity: 1 }} exit={{ height: 0, opacity: 0 }} className="overflow-hidden">
            {folder.children!.map((c) => (
              <FolderNode key={c.id} folder={c} depth={depth + 1} onDelete={onDelete} onAddChild={onAddChild} />
            ))}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

export default function AdminFolders() {
  const qc = useQueryClient();
  const [showCreate, setShowCreate] = useState(false);
  const [newLang, setNewLang] = useState("vostfr");
  const [newSeason, setNewSeason] = useState(1);
  const [pendingParent, setPendingParent] = useState<{ parentId: number; animeId?: number; type: string } | null>(null);

  const { data: folders = [], isLoading } = useQuery({
    queryKey: ["admin-folders"],
    queryFn: adminListFolders,
  });

  const deleteMutation = useMutation({
    mutationFn: (id: number) => adminDeleteFolder(id),
    onSuccess: () => {
      toast.success("Dossier supprimé");
      qc.invalidateQueries({ queryKey: ["admin-folders"] });
    },
    onError: (err: unknown) => {
      toast.error(getApiError(err, "Erreur lors de la suppression"));
    },
  });

  const createMutation = useMutation({
    mutationFn: (data: Record<string, unknown>) => adminCreateFolder(data),
    onSuccess: () => {
      toast.success("Dossier créé !");
      qc.invalidateQueries({ queryKey: ["admin-folders"] });
      setPendingParent(null);
    },
    onError: (err: unknown) => toast.error(getApiError(err, "Erreur lors de la création")),
  });

  const handleDelete = (id: number) => {
    if (confirm("Supprimer ce dossier ?")) deleteMutation.mutate(id);
  };

  const handleAddChild = (parentId: number, animeId: number | undefined, folderType: string) => {
    setPendingParent({ parentId, animeId, type: folderType });
  };

  const handleCreateChild = () => {
    if (!pendingParent) return;
    createMutation.mutate({
      anime_id: pendingParent.animeId ?? null,
      name: pendingParent.type === "language" ? newLang.toUpperCase() : `Saison ${newSeason}`,
      folder_type: pendingParent.type,
      language: pendingParent.type === "language" ? newLang : null,
      season_number: pendingParent.type === "season" ? newSeason : null,
      parent_id: pendingParent.parentId,
    });
  };

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="font-display font-extrabold text-3xl mb-1">Dossiers</h1>
          <p className="text-muted-foreground font-body">Arborescence des animés, langues et saisons.</p>
        </div>
      </div>

      {pendingParent && (
        <div className="bg-surface border border-primary/30 rounded-xl p-4 mb-4">
          <h3 className="font-display font-bold text-sm mb-3">
            Créer un sous-dossier {pendingParent.type === "language" ? "(Langue)" : "(Saison)"}
          </h3>
          <div className="flex gap-3 items-end">
            {pendingParent.type === "language" ? (
              <div>
                <label className="text-[11px] uppercase tracking-wider text-muted-foreground font-body font-semibold">Langue</label>
                <select
                  value={newLang}
                  onChange={(e) => setNewLang(e.target.value)}
                  className="mt-1 block bg-surface-2 border border-border rounded-lg px-3 py-2 text-sm font-body"
                >
                  <option value="vostfr">VOSTFR</option>
                  <option value="vf">VF</option>
                </select>
              </div>
            ) : (
              <div>
                <label className="text-[11px] uppercase tracking-wider text-muted-foreground font-body font-semibold">Saison N°</label>
                <input
                  type="number"
                  min={1}
                  value={newSeason}
                  onChange={(e) => setNewSeason(Number(e.target.value))}
                  className="mt-1 block w-24 bg-surface-2 border border-border rounded-lg px-3 py-2 text-sm font-body"
                />
              </div>
            )}
            <button
              onClick={handleCreateChild}
              disabled={createMutation.isPending}
              className="px-4 py-2 rounded-lg bg-primary text-primary-foreground text-sm font-body font-semibold disabled:opacity-50"
            >
              {createMutation.isPending ? "Création..." : "Créer"}
            </button>
            <button
              onClick={() => setPendingParent(null)}
              className="px-4 py-2 rounded-lg bg-surface border border-border text-sm font-body font-semibold"
            >
              Annuler
            </button>
          </div>
        </div>
      )}

      {isLoading ? (
        <div className="flex justify-center py-12"><Loader2 className="w-6 h-6 animate-spin text-primary" /></div>
      ) : (
        <div className="bg-surface border border-border rounded-xl p-4">
          {folders.length === 0 && (
            <p className="text-sm text-muted-foreground font-body py-8 text-center">
              Aucun dossier. Crée d'abord un anime dans l'onglet Animés.
            </p>
          )}
          {folders.map((f: FolderItem) => (
            <FolderNode key={f.id} folder={f} onDelete={handleDelete} onAddChild={handleAddChild} />
          ))}
        </div>
      )}
    </div>
  );
}
