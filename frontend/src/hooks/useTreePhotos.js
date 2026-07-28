import { useEffect, useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";

import { fetchTreeObservations } from "@/api/datasets.js";

// Legacy photos live in Firebase buckets, and the arbocensus-8ac1d one answers
// 402 for every object since its billing was closed. Probing each URL is the
// only way to tell a live photo from a dead one before showing it.
export default function useTreePhotos(treeId) {
  const { data } = useQuery({
    queryKey: ["tree-observations", treeId],
    queryFn: () => fetchTreeObservations(treeId),
    enabled: !!treeId,
  });

  const candidates = useMemo(
    () =>
      Array.from(
        new Set(
          (data ?? []).flatMap((entry) =>
            entry.photo_urls?.length
              ? entry.photo_urls
              : [entry.photo || entry.photo_url].filter(Boolean),
          ),
        ),
      ),
    [data],
  );
  const [photos, setPhotos] = useState([]);

  useEffect(() => {
    if (candidates.length === 0) {
      setPhotos([]);
      return undefined;
    }
    let cancelled = false;
    Promise.all(
      candidates.map(
        (src) =>
          new Promise((resolve) => {
            const image = new Image();
            image.onload = () => resolve(src);
            image.onerror = () => resolve(null);
            image.src = src;
          }),
      ),
    ).then((results) => {
      if (!cancelled) setPhotos(results.filter(Boolean));
    });
    return () => {
      cancelled = true;
    };
  }, [candidates]);

  return photos;
}
