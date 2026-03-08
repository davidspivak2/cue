import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";

type WorkbenchSkeletonProps = {
  isNarrow?: boolean;
  className?: string;
};

export function WorkbenchSkeleton({
  isNarrow = false,
  className
}: WorkbenchSkeletonProps) {
  return (
    <div
      data-testid="workbench"
      className={cn("flex h-full min-h-0 flex-col gap-4", className)}
      aria-busy="true"
      aria-label="Loading workbench"
    >
      <header
        className="flex items-center gap-2 pb-2"
        data-testid="workbench-top-bar"
      >
        <div className="flex min-w-0 flex-1 items-center gap-2">
          <Skeleton className="h-6 w-40 max-w-[280px]" />
        </div>
        <div className="min-w-0 flex-1" aria-hidden="true" />
        <Skeleton className="h-9 w-20 shrink-0" />
      </header>

      <div
        className={cn(
          "flex min-h-0 flex-1 gap-4",
          isNarrow ? "flex-col" : "flex-row"
        )}
      >
        <section
          className="flex min-h-[220px] flex-1 items-center justify-center"
          data-testid="workbench-center-panel"
        >
          <Skeleton className="h-full w-full rounded-md" />
        </section>

        {!isNarrow && (
          <section
            className="flex min-h-0 w-88 shrink-0 flex-col rounded-lg border border-border bg-card xl:w-96"
            data-testid="workbench-right-panel"
          >
            <div className="border-b border-border px-4 py-2">
              <Skeleton className="h-4 w-12" />
            </div>
            <div
              className="min-h-0 flex-1 space-y-4 py-4 px-4"
              style={{ scrollbarGutter: "stable" }}
            >
              <Skeleton className="h-9 w-full" />
              <Skeleton className="h-9 w-full" />
              <Skeleton className="h-9 w-3/4" />
              <Skeleton className="h-16 w-full" />
              <Skeleton className="h-9 w-full" />
              <Skeleton className="h-9 w-2/3" />
            </div>
          </section>
        )}
      </div>
    </div>
  );
}
