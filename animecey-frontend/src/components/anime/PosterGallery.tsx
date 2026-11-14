import { useEffect, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";

interface Props {
  title: string;
  /** La 1re est l'affiche principale, les suivantes viennent du bot (/poster). */
  posters: string[];
}

/**
 * Affiche du titre. Avec plusieurs affiches : glisser (ou toucher) pour passer à la suivante,
 * défilement automatique toutes les 6 s tant que le visiteur n'a rien touché.
 */
export function PosterGallery({ title, posters }: Props) {
  const [index, setIndex] = useState(0);
  const [touched, setTouched] = useState(false);
  const count = posters.length;

  useEffect(() => {
    setIndex(0);
  }, [posters.join("|")]);

  useEffect(() => {
    if (count < 2 || touched) return;
    const t = setInterval(() => setIndex((i) => (i + 1) % count), 6000);
    return () => clearInterval(t);
  }, [count, touched]);

  const go = (delta: number) => {
    setTouched(true);
    setIndex((i) => (i + delta + count) % count);
  };

  if (count === 0) return null;

  return (
    <div className="flex flex-col items-center">
      <div className="relative w-[180px] md:w-[230px] aspect-[2/3] rounded-2xl overflow-hidden shadow-card ring-1 ring-foreground/10 -rotate-1 hover:rotate-0 transition-transform bg-card">
        <AnimatePresence initial={false} mode="popLayout">
          <motion.img
            key={posters[index]}
            src={posters[index]}
            alt={index === 0 ? title : `${title} — affiche ${index + 1}`}
            className="absolute inset-0 w-full h-full object-cover"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.35 }}
            drag={count > 1 ? "x" : false}
            dragConstraints={{ left: 0, right: 0 }}
            dragElastic={0.4}
            onDragEnd={(_, info) => {
              if (info.offset.x < -40) go(1);
              else if (info.offset.x > 40) go(-1);
            }}
            onClick={() => count > 1 && go(1)}
            draggable={false}
          />
        </AnimatePresence>
      </div>
      {count > 1 && (
        <div className="mt-3 flex items-center gap-1.5" role="tablist" aria-label="Affiches">
          {posters.map((_, i) => (
            <button
              key={i}
              type="button"
              role="tab"
              aria-selected={i === index}
              aria-label={`Affiche ${i + 1}`}
              onClick={() => {
                setTouched(true);
                setIndex(i);
              }}
              className={`h-1.5 rounded-full transition-all ${i === index ? "w-5 bg-primary" : "w-1.5 bg-foreground/30"}`}
            />
          ))}
        </div>
      )}
    </div>
  );
}
