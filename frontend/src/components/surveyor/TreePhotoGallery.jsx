import { useEffect, useState } from "react";
import { ChevronLeft, ChevronRight } from "lucide-react";

import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { cn } from "@/lib/utils";

export default function TreePhotoGallery({ open, onOpenChange, title, photos }) {
  const [index, setIndex] = useState(0);
  const [touchStartX, setTouchStartX] = useState(null);

  useEffect(() => {
    if (open) setIndex(0);
  }, [open]);

  const last = photos.length - 1;
  const show = (next) => setIndex(Math.min(Math.max(next, 0), last));

  const handleTouchEnd = (event) => {
    if (touchStartX == null) return;
    const delta = event.changedTouches[0].clientX - touchStartX;
    setTouchStartX(null);
    if (Math.abs(delta) < 40) return;
    show(delta < 0 ? index + 1 : index - 1);
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent
        className="z-[1200] max-w-md gap-3 p-4"
        onKeyDown={(event) => {
          if (event.key === "ArrowLeft") show(index - 1);
          if (event.key === "ArrowRight") show(index + 1);
        }}
      >
        <DialogHeader>
          <DialogTitle className="text-center">{title}</DialogTitle>
        </DialogHeader>
        <div
          className="relative aspect-square overflow-hidden rounded-lg bg-slate-900"
          onTouchStart={(event) => setTouchStartX(event.touches[0].clientX)}
          onTouchEnd={handleTouchEnd}
        >
          {photos[index] && (
            <img
              src={photos[index]}
              alt={title}
              className="h-full w-full object-contain"
            />
          )}
          {index > 0 && (
            <button
              type="button"
              aria-label="Foto anterior"
              onClick={() => show(index - 1)}
              className="absolute left-1 top-1/2 flex h-11 w-11 -translate-y-1/2 items-center justify-center rounded-full bg-black/50 text-white"
            >
              <ChevronLeft className="h-6 w-6" aria-hidden="true" />
            </button>
          )}
          {index < last && (
            <button
              type="button"
              aria-label="Foto siguiente"
              onClick={() => show(index + 1)}
              className="absolute right-1 top-1/2 flex h-11 w-11 -translate-y-1/2 items-center justify-center rounded-full bg-black/50 text-white"
            >
              <ChevronRight className="h-6 w-6" aria-hidden="true" />
            </button>
          )}
        </div>
        {photos.length > 1 && (
          <div className="flex justify-center gap-1.5">
            {photos.map((src, position) => (
              <span
                key={src}
                className={cn(
                  "h-1.5 w-1.5 rounded-full",
                  position === index ? "bg-slate-900" : "bg-slate-300",
                )}
              />
            ))}
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}
