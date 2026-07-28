import { Component } from "react";

export default class ErrorBoundary extends Component {
  state = { hasError: false };

  static getDerivedStateFromError() {
    return { hasError: true };
  }

  componentDidCatch(error, info) {
    console.error("Uncaught render error", error, info);
  }

  render() {
    if (this.state.hasError) {
      return (
        <main className="flex min-h-screen flex-col items-center justify-center gap-4 bg-slate-50 p-8 text-center">
          <p className="text-lg font-medium text-slate-700">
            Ocurrió un error inesperado.
          </p>
          <button
            type="button"
            onClick={() => window.location.reload()}
            className="rounded bg-slate-900 px-4 py-2 text-sm font-medium text-white"
          >
            Recargar página
          </button>
        </main>
      );
    }

    return this.props.children;
  }
}
