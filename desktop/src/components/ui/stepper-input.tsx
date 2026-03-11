import * as React from "react";

import type { ButtonProps } from "@/components/ui/button";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { cn } from "@/lib/utils";

const HOLD_DELAY_MS = 325;
const HOLD_INTERVAL_MS = 75;

const clampNumber = (value: number, min: number, max: number) =>
  Math.min(max, Math.max(min, value));

const getStepPrecision = (step: number) => {
  const stepText = step.toString().toLowerCase();
  if (stepText.includes("e-")) {
    return Number.parseInt(stepText.split("e-")[1] ?? "0", 10);
  }
  const [, decimals = ""] = stepText.split(".");
  return decimals.length;
};

const roundToPrecision = (value: number, precision: number) => {
  if (precision <= 0) {
    return Math.round(value);
  }
  return Number(value.toFixed(precision));
};

const getNextStepValue = (
  value: number,
  delta: number,
  step: number,
  min: number,
  max: number
) => {
  const precision = getStepPrecision(step);
  return clampNumber(roundToPrecision(value + delta * step, precision), min, max);
};

const getDisplayValue = (value: number, step: number) => {
  if (step >= 1) {
    return String(Math.round(value));
  }
  if (step >= 0.1) {
    return value.toFixed(1);
  }
  return value.toFixed(2);
};

export type StepperInputProps = {
  value: number;
  min: number;
  max: number;
  step: number;
  "aria-label"?: string;
  "data-testid"?: string;
  className?: string;
  inputClassName?: string;
  buttonClassName?: string;
  buttonSize?: ButtonProps["size"];
  onChange: (value: number) => void;
};

export const StepperInput = ({
  value,
  min,
  max,
  step,
  "aria-label": ariaLabel,
  "data-testid": dataTestId,
  className,
  inputClassName,
  buttonClassName,
  buttonSize = "iconSm",
  onChange
}: StepperInputProps) => {
  const valueRef = React.useRef(value);
  const onChangeRef = React.useRef(onChange);
  const holdTimeoutRef = React.useRef<number | null>(null);
  const holdIntervalRef = React.useRef<number | null>(null);
  const ignoreClickRef = React.useRef(false);

  React.useEffect(() => {
    valueRef.current = value;
  }, [value]);

  React.useEffect(() => {
    onChangeRef.current = onChange;
  }, [onChange]);

  const stopRepeat = React.useCallback(() => {
    if (holdTimeoutRef.current !== null) {
      window.clearTimeout(holdTimeoutRef.current);
      holdTimeoutRef.current = null;
    }
    if (holdIntervalRef.current !== null) {
      window.clearInterval(holdIntervalRef.current);
      holdIntervalRef.current = null;
    }
  }, []);

  React.useEffect(() => stopRepeat, [stopRepeat]);

  const applyStep = React.useCallback(
    (delta: number) => {
      const current = valueRef.current;
      const next = getNextStepValue(current, delta, step, min, max);
      if (Math.abs(next - current) < Number.EPSILON) {
        stopRepeat();
        return;
      }
      valueRef.current = next;
      onChangeRef.current(next);
    },
    [max, min, step, stopRepeat]
  );

  const startRepeat = React.useCallback(
    (delta: number) => {
      stopRepeat();
      applyStep(delta);
      holdTimeoutRef.current = window.setTimeout(() => {
        holdIntervalRef.current = window.setInterval(() => {
          applyStep(delta);
        }, HOLD_INTERVAL_MS);
      }, HOLD_DELAY_MS);
    },
    [applyStep, stopRepeat]
  );

  const handlePointerDown =
    (delta: number) => (event: React.PointerEvent<HTMLButtonElement>) => {
      if (
        event.pointerType !== "touch" &&
        event.pointerType !== "pen" &&
        event.button !== 0
      ) {
        return;
      }
      ignoreClickRef.current = true;
      startRepeat(delta);
      event.currentTarget.setPointerCapture?.(event.pointerId);
    };

  const handleKeyDown =
    (delta: number) => (event: React.KeyboardEvent<HTMLButtonElement>) => {
      if (event.key !== " " && event.key !== "Enter") {
        return;
      }
      if (event.repeat) {
        event.preventDefault();
        return;
      }
      event.preventDefault();
      ignoreClickRef.current = true;
      startRepeat(delta);
    };

  const handleKeyUp = (event: React.KeyboardEvent<HTMLButtonElement>) => {
    if (event.key !== " " && event.key !== "Enter") {
      return;
    }
    stopRepeat();
  };

  const handleClick =
    (delta: number) => (event: React.MouseEvent<HTMLButtonElement>) => {
      if (ignoreClickRef.current) {
        ignoreClickRef.current = false;
        event.preventDefault();
        return;
      }
      applyStep(delta);
    };

  return (
    <div
      className={cn(
        "flex h-8 items-stretch overflow-hidden rounded-md border border-input bg-background",
        className
      )}
    >
      <Button
        type="button"
        variant="ghost"
        size={buttonSize}
        className={cn("h-full w-7 rounded-none px-0", buttonClassName)}
        aria-label={ariaLabel ? `Decrease ${ariaLabel.toLowerCase()}` : undefined}
        data-testid={dataTestId ? `${dataTestId}-decrease` : undefined}
        onClick={handleClick(-1)}
        onPointerDown={handlePointerDown(-1)}
        onPointerUp={stopRepeat}
        onPointerCancel={stopRepeat}
        onLostPointerCapture={stopRepeat}
        onBlur={stopRepeat}
        onKeyDown={handleKeyDown(-1)}
        onKeyUp={handleKeyUp}
        disabled={value <= min}
      >
        <span className="text-xs leading-none">-</span>
      </Button>
      <Input
        type="number"
        className={cn(
          "h-full w-14 rounded-none border-0 bg-transparent px-2 text-center text-xs focus-visible:ring-0",
          inputClassName
        )}
        min={min}
        max={max}
        step={step}
        value={getDisplayValue(value, step)}
        aria-label={ariaLabel}
        data-testid={dataTestId}
        onChange={(event) => {
          const nextValue = Number(event.target.value);
          if (!Number.isNaN(nextValue)) {
            onChange(clampNumber(nextValue, min, max));
          }
        }}
      />
      <Button
        type="button"
        variant="ghost"
        size={buttonSize}
        className={cn("h-full w-7 rounded-none px-0", buttonClassName)}
        aria-label={ariaLabel ? `Increase ${ariaLabel.toLowerCase()}` : undefined}
        data-testid={dataTestId ? `${dataTestId}-increase` : undefined}
        onClick={handleClick(1)}
        onPointerDown={handlePointerDown(1)}
        onPointerUp={stopRepeat}
        onPointerCancel={stopRepeat}
        onLostPointerCapture={stopRepeat}
        onBlur={stopRepeat}
        onKeyDown={handleKeyDown(1)}
        onKeyUp={handleKeyUp}
        disabled={value >= max}
      >
        <span className="text-xs leading-none">+</span>
      </Button>
    </div>
  );
};
