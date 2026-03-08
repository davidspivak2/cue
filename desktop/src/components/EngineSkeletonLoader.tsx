import { Skeleton } from "@/components/ui/skeleton";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow
} from "@/components/ui/table";
import { cn } from "@/lib/utils";

type Variant = "hub" | "settings";
type HubViewMode = "cards" | "list";

const DEFAULT_HUB_SKELETON_COUNT = 6;
const MAX_HUB_SKELETON_COUNT = 24;

type EngineSkeletonLoaderProps = {
  variant: Variant;
  hubView?: HubViewMode;
  className?: string;
  projectCount?: number;
};

function HubCardsSkeleton({
  className,
  count = DEFAULT_HUB_SKELETON_COUNT
}: {
  className?: string;
  count?: number;
}) {
  const n = Math.min(Math.max(1, Math.floor(count)), MAX_HUB_SKELETON_COUNT);
  return (
    <div
      className={cn("grid gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4", className)}
      aria-busy="true"
      aria-label="Loading projects"
    >
      {Array.from({ length: n }, (_, i) => (
        <div
          key={i + 1}
          className="rounded-lg border border-border bg-card p-3 shadow-sm"
        >
          <Skeleton
            className="w-full overflow-hidden rounded-lg border border-border"
            style={{ aspectRatio: "16 / 9" }}
          />
          <div className="mt-3 space-y-2">
            <Skeleton className="h-4 w-full max-w-[85%]" />
            <Skeleton className="h-3 w-16" />
            <Skeleton className="h-4 w-24" />
          </div>
        </div>
      ))}
    </div>
  );
}

function HubListSkeleton({
  className,
  count = DEFAULT_HUB_SKELETON_COUNT
}: {
  className?: string;
  count?: number;
}) {
  const rowCount = Math.min(Math.max(1, Math.floor(count)), MAX_HUB_SKELETON_COUNT);
  return (
    <div
      className={cn(
        "overflow-x-auto rounded-lg border border-border bg-muted/50 dark:bg-muted/30",
        className
      )}
      aria-busy="true"
      aria-label="Loading projects"
    >
      <Table className="table-fixed w-full">
        <TableHeader>
          <TableRow>
            <TableHead scope="col" className="min-w-0 px-2" style={{ width: "calc((100% - 60px) / 4)" }}>Video</TableHead>
            <TableHead scope="col" className="min-w-0 pl-2 pr-6" style={{ width: "calc((100% - 60px) / 4)" }}>Duration</TableHead>
            <TableHead scope="col" className="min-w-0 pl-6 pr-2" style={{ width: "calc((100% - 60px) / 4)" }}>Status</TableHead>
            <TableHead scope="col" className="min-w-0 px-2" style={{ width: "calc((100% - 60px) / 4)" }}>Progress</TableHead>
            <TableHead scope="col" className="w-[60px] shrink-0 px-2">
              <span className="sr-only">Actions</span>
            </TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {Array.from({ length: rowCount }, (_, i) => (
            <TableRow key={i} className="hover:bg-transparent!">
              <TableCell className="min-w-0 overflow-hidden px-2">
                <div className="flex min-w-0 items-center gap-2">
                  <Skeleton
                    className="h-9 w-14 shrink-0 rounded border border-border"
                    style={{ aspectRatio: "16 / 9" }}
                  />
                  <Skeleton className="h-4 min-w-0 flex-1 max-w-full" />
                </div>
              </TableCell>
              <TableCell className="min-w-0 pl-2 pr-6">
                <Skeleton className="h-4 w-12" />
              </TableCell>
              <TableCell className="min-w-0 pl-6 pr-2">
                <Skeleton className="h-5 max-w-full rounded-md" />
              </TableCell>
              <TableCell className="min-w-0 overflow-hidden px-2">
                <Skeleton className="h-4 max-w-full" />
              </TableCell>
              <TableCell className="w-[60px] shrink-0 px-2">
                <Skeleton className="h-8 w-8 rounded" />
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  );
}

function EngineSkeletonLoader({
  variant,
  hubView = "cards",
  className,
  projectCount
}: EngineSkeletonLoaderProps) {
  if (variant === "hub") {
    const count =
      projectCount !== undefined && projectCount > 0
        ? projectCount
        : DEFAULT_HUB_SKELETON_COUNT;
    return hubView === "cards" ? (
      <HubCardsSkeleton className={className} count={count} />
    ) : (
      <HubListSkeleton className={className} count={count} />
    );
  }

  return (
    <div
      className={cn("flex flex-col gap-4 pb-6", className)}
      aria-busy="true"
      aria-label="Loading settings"
    >
      {[1, 2, 3].map((i) => (
        <section
          key={i}
          className="rounded-lg border border-border bg-card p-6 shadow-sm"
        >
          <Skeleton className="h-6 w-32" />
          <div className="mt-4 space-y-3">
            <Skeleton className="h-9 w-full max-w-xs" />
            <Skeleton className="h-4 w-2/3" />
          </div>
        </section>
      ))}
    </div>
  );
}

export default EngineSkeletonLoader;
