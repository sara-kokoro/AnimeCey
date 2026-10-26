export function SkeletonCard() {
  return (
    <div className="shrink-0 w-[150px] md:w-[180px]">
      <div className="aspect-[2/3] rounded-xl shimmer" />
      <div className="h-3 mt-2 rounded shimmer w-4/5" />
      <div className="h-2.5 mt-1.5 rounded shimmer w-2/5" />
    </div>
  );
}

export function SkeletonEpisode() {
  return (
    <div className="flex gap-3 p-2">
      <div className="w-[120px] md:w-[160px] aspect-video rounded-lg shimmer shrink-0" />
      <div className="flex-1 space-y-2 py-1">
        <div className="h-3.5 rounded shimmer w-3/4" />
        <div className="h-2.5 rounded shimmer w-1/4" />
        <div className="h-2.5 rounded shimmer w-2/5 mt-4" />
      </div>
    </div>
  );
}