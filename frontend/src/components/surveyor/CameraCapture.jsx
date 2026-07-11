import { useEffect, useRef, useState } from "react";
import { X } from "lucide-react";
import { Button } from "@/components/ui/button";

export default function CameraCapture({ onCapture, onClose }) {
  const videoRef = useRef(null);
  const streamRef = useRef(null);
  const [error, setError] = useState(null);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    let cancelled = false;

    async function start() {
      if (!navigator.mediaDevices?.getUserMedia) {
        setError(
          "Este navegador no puede abrir la cámara. Usa una versión reciente de Chrome o Safari con conexión segura (https)."
        );
        return;
      }
      try {
        const stream = await navigator.mediaDevices.getUserMedia({
          video: { facingMode: { ideal: "environment" } },
          audio: false,
        });
        if (cancelled) {
          stream.getTracks().forEach((track) => track.stop());
          return;
        }
        streamRef.current = stream;
        videoRef.current.srcObject = stream;
      } catch {
        if (!cancelled) {
          setError(
            "No se pudo abrir la cámara. Revisa que el navegador tenga permiso para usarla."
          );
        }
      }
    }

    start();
    return () => {
      cancelled = true;
      streamRef.current?.getTracks().forEach((track) => track.stop());
    };
  }, []);

  const takePhoto = () => {
    const video = videoRef.current;
    const canvas = document.createElement("canvas");
    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;
    canvas.getContext("2d").drawImage(video, 0, 0);
    canvas.toBlob(
      (blob) => {
        if (!blob) return;
        onCapture(
          new File([blob], `tree-${Date.now()}.jpg`, { type: "image/jpeg" })
        );
      },
      "image/jpeg",
      0.85
    );
  };

  return (
    <div className="fixed inset-0 z-[1300] flex flex-col bg-black">
      <div className="flex items-center justify-between px-4 py-3">
        <p className="text-sm font-semibold text-white">Foto del árbol</p>
        <button
          type="button"
          aria-label="Cerrar cámara"
          onClick={onClose}
          className="rounded-full bg-white/15 p-2 text-white"
        >
          <X className="h-5 w-5" />
        </button>
      </div>

      {error ? (
        <div className="flex flex-1 flex-col items-center justify-center gap-4 px-8 text-center">
          <p className="text-sm text-white">{error}</p>
          <Button type="button" variant="secondary" onClick={onClose}>
            Volver
          </Button>
        </div>
      ) : (
        <>
          <video
            ref={videoRef}
            autoPlay
            playsInline
            muted
            onLoadedMetadata={() => setReady(true)}
            className="min-h-0 flex-1 object-cover"
          />
          <div className="flex items-center justify-center py-6">
            <button
              type="button"
              aria-label="Tomar foto"
              onClick={takePhoto}
              disabled={!ready}
              className="h-16 w-16 rounded-full border-4 border-white bg-white/30 transition active:scale-95 disabled:opacity-40"
            />
          </div>
        </>
      )}
    </div>
  );
}
