import { useEffect } from "react";
import { useToastStore } from "@/store/toastStore.js";
import { cn } from "@/lib/utils";

function ToastItem({ toast }) {
  const dismiss = useToastStore((state) => state.dismiss);
  useEffect(() => {
    const timer = setTimeout(() => dismiss(toast.id), 5000);
    return () => clearTimeout(timer);
  }, [toast.id, dismiss]);

  return (
    <div
      role="status"
      className={cn(
        "rounded-md border px-4 py-3 text-sm shadow-md",
        toast.variant === "error"
          ? "border-destructive/50 bg-destructive text-destructive-foreground"
          : "border-transparent bg-primary text-primary-foreground",
      )}
    >
      {toast.message}
    </div>
  );
}

export function Toaster() {
  const toasts = useToastStore((state) => state.toasts);
  return (
    <div className="fixed bottom-4 right-4 z-50 flex w-80 flex-col gap-2">
      {toasts.map((toast) => (
        <ToastItem key={toast.id} toast={toast} />
      ))}
    </div>
  );
}
