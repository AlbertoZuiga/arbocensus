import "fake-indexeddb/auto";
// jsdom's File is not structured-cloneable in Node, which browsers' is.
import { File, Blob } from "node:buffer";
import { describe, it, expect } from "vitest";
import { createSyncStoragePersister } from "@tanstack/query-sync-storage-persister";
import { createIdbPersister } from "./idbPersister.js";

function clientWithQueuedPhoto(photo) {
  return {
    timestamp: Date.now(),
    buster: "v1",
    clientState: {
      queries: [],
      mutations: [
        {
          mutationKey: ["visitStop"],
          state: {
            isPaused: true,
            variables: {
              stopId: "stop-1",
              status: "alive",
              notes: "árbol sano",
              photo,
            },
          },
        },
      ],
    },
  };
}

describe("createIdbPersister", () => {
  it("restores the queued photo with its bytes, not as an empty object", async () => {
    const persister = createIdbPersister("arbocensus.test-cache");
    const photo = new File(["jpeg-bytes"], "tree.jpg", { type: "image/jpeg" });

    await persister.persistClient(clientWithQueuedPhoto(photo));
    const restored = await persister.restoreClient();

    // Node 20 clones a File down to a Blob; browsers keep the File subclass.
    const restoredPhoto = restored.clientState.mutations[0].state.variables.photo;
    expect(restoredPhoto).toBeInstanceOf(Blob);
    expect(restoredPhoto.type).toBe("image/jpeg");
    expect(await restoredPhoto.text()).toBe("jpeg-bytes");
  });

  it("drops the cache when it is removed", async () => {
    const persister = createIdbPersister("arbocensus.test-cache");
    await persister.persistClient(clientWithQueuedPhoto(null));

    await persister.removeClient();

    expect(await persister.restoreClient()).toBeUndefined();
  });

  it("loses the photo through the localStorage persister it replaces", async () => {
    const persister = createSyncStoragePersister({
      storage: globalThis.localStorage,
      key: "arbocensus.legacy-cache",
      throttleTime: 0,
    });
    const photo = new File(["jpeg-bytes"], "tree.jpg", { type: "image/jpeg" });

    persister.persistClient(clientWithQueuedPhoto(photo));
    await new Promise((resolve) => setTimeout(resolve, 0));
    const restored = await persister.restoreClient();

    expect(restored.clientState.mutations[0].state.variables.photo).toEqual({});
  });
});
