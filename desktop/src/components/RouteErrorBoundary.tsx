import * as React from "react";
import { BACKEND_UNREACHABLE_MESSAGE } from "@/backendHealth";

type Props = {
  children: React.ReactNode;
};

type State = {
  error: Error | null;
};

export class RouteErrorBoundary extends React.Component<Props, State> {
  state: State = { error: null };

  static getDerivedStateFromError(error: Error): State {
    return { error };
  }

  componentDidCatch(error: Error, errorInfo: React.ErrorInfo) {
    console.error("RouteErrorBoundary caught:", error, errorInfo);
  }

  retry = () => {
    this.setState({ error: null });
  };

  render() {
    if (this.state.error) {
      return (
        <div
          className="flex min-h-[50vh] flex-1 flex-col items-center justify-center px-6 py-12"
          data-testid="route-error-boundary"
        >
          <p className="w-full max-w-md text-center text-sm text-destructive">
            {BACKEND_UNREACHABLE_MESSAGE}
          </p>
          <button
            type="button"
            onClick={this.retry}
            className="mt-4 text-sm text-primary underline underline-offset-2 hover:no-underline"
          >
            Try again
          </button>
        </div>
      );
    }
    return this.props.children;
  }
}
