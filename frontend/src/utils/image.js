export const MAX_PHOTO_SIDE = 1600;
export const PHOTO_JPEG_QUALITY = 0.8;

export function fitWithin(width, height, maxSide = MAX_PHOTO_SIDE) {
  const largest = Math.max(width, height);
  if (largest <= maxSide) return { width, height };
  const scale = maxSide / largest;
  return {
    width: Math.round(width * scale),
    height: Math.round(height * scale),
  };
}

export function captureJpegFrame(video, filename) {
  const { width, height } = fitWithin(video.videoWidth, video.videoHeight);
  const canvas = document.createElement("canvas");
  canvas.width = width;
  canvas.height = height;
  canvas.getContext("2d").drawImage(video, 0, 0, width, height);
  return new Promise((resolve) => {
    canvas.toBlob(
      (blob) =>
        resolve(
          blob ? new File([blob], filename, { type: "image/jpeg" }) : null
        ),
      "image/jpeg",
      PHOTO_JPEG_QUALITY
    );
  });
}
