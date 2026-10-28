export default function SkeletonCard() {
  return (
    <div className="overflow-hidden rounded-card border border-zinc-200/80 dark:border-white/5">
      <div className="aspect-square w-full animate-pulse bg-zinc-200/60 dark:bg-white/5" />
      <div className="space-y-2 p-3">
        <div className="h-3 w-4/5 animate-pulse rounded bg-zinc-200/60 dark:bg-white/5" />
        <div className="h-3 w-2/5 animate-pulse rounded bg-zinc-200/60 dark:bg-white/5" />
      </div>
    </div>
  );
}
