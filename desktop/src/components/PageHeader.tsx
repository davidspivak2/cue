import * as React from "react";
import { ArrowLeft, Settings } from "lucide-react";
import { useNavigate } from "react-router-dom";

import { Button } from "@/components/ui/button";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger
} from "@/components/ui/tooltip";

export type PageHeaderProps = {
  title: React.ReactNode;
  showBack?: boolean;
  onBack?: () => void;
  right?: React.ReactNode;
  onOpenSettings: () => void;
  showSettings?: boolean;
  settingsDisabled?: boolean;
  settingsDisabledTooltip?: string;
};

const PageHeader = ({
  title,
  showBack = false,
  onBack,
  right,
  onOpenSettings,
  showSettings = true,
  settingsDisabled = false,
  settingsDisabledTooltip
}: PageHeaderProps) => {
  const navigate = useNavigate();
  const handleBack = onBack ?? (() => navigate("/"));

  return (
    <header className="flex flex-wrap items-center justify-between gap-3">
      <div className="flex min-w-0 flex-1 items-center gap-3">
        {showBack && (
          <Button
            variant="ghost"
            size="sm"
            className="gap-2 shrink-0"
            onClick={handleBack}
          >
            <ArrowLeft className="h-4 w-4" />
            Back
          </Button>
        )}
        <div className="min-w-0">{title}</div>
      </div>
      <div className="flex items-center gap-2">
        {right}
        {showSettings && (
          <TooltipProvider>
            <Tooltip>
              <TooltipTrigger asChild>
                <span>
                  <Button
                    variant="ghost"
                    size="icon"
                    aria-label="Settings"
                    disabled={settingsDisabled}
                    onClick={() => !settingsDisabled && onOpenSettings()}
                  >
                    <Settings className="h-4 w-4" />
                  </Button>
                </span>
              </TooltipTrigger>
              <TooltipContent>
                {settingsDisabled && settingsDisabledTooltip
                  ? settingsDisabledTooltip
                  : "Settings"}
              </TooltipContent>
            </Tooltip>
          </TooltipProvider>
        )}
      </div>
    </header>
  );
};

export default PageHeader;
