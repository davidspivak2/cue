import * as React from "react";
import { CheckCircle2, Circle, Loader2, SkipForward, XCircle } from "lucide-react";

import { cn } from "@/lib/utils";

export type ChecklistState = "pending" | "active" | "done" | "skipped" | "failed";

export type ChecklistItem = {
  id: string;
  label: string;
  state?: ChecklistState;
  detail?: string | null;
};

export type ChecklistProps = {
  items: ChecklistItem[];
} & React.HTMLAttributes<HTMLDivElement>;

const stateIconMap: Record<ChecklistState, React.ElementType> = {
  pending: Circle,
  active: Loader2,
  done: CheckCircle2,
  skipped: SkipForward,
  failed: XCircle
};

const stateColorMap: Record<ChecklistState, string> = {
  pending: "text-muted-foreground",
  active: "text-primary",
  done: "text-primary",
  skipped: "text-muted-foreground",
  failed: "text-destructive"
};

const Checklist = ({ items, className, ...props }: ChecklistProps) => (
  <div className={cn("flex flex-col gap-2", className)} {...props}>
    {items.map((item) => {
      const state = item.state ?? "pending";
      const Icon = stateIconMap[state];
      const detail = item.detail?.trim();
      return (
        <div key={item.id} className="flex items-start gap-2">
          <Icon
            className={cn(
              "mt-0.5 h-4 w-4",
              state === "active" ? "animate-spin" : "",
              stateColorMap[state]
            )}
          />
          <div className="min-w-0 flex-1">
            <p className="text-sm leading-5 text-foreground">
              <span>{item.label}</span>
              {detail && (
                <>
                  <span className="mx-1 text-muted-foreground" aria-hidden="true">
                    &bull;
                  </span>
                  <span className="text-xs text-muted-foreground">{detail}</span>
                </>
              )}
            </p>
          </div>
        </div>
      );
    })}
  </div>
);

export default Checklist;
