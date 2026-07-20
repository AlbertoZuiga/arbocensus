const DB_NAME = "arbocensus";
const DB_VERSION = 1;
const STORE_NAME = "query-cache";

function openDatabase() {
  return new Promise((resolve, reject) => {
    const request = indexedDB.open(DB_NAME, DB_VERSION);
    request.onupgradeneeded = () => {
      request.result.createObjectStore(STORE_NAME);
    };
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error);
  });
}

async function withStore(mode, run) {
  const db = await openDatabase();
  try {
    return await new Promise((resolve, reject) => {
      const transaction = db.transaction(STORE_NAME, mode);
      const request = run(transaction.objectStore(STORE_NAME));
      transaction.oncomplete = () => resolve(request?.result);
      transaction.onabort = () => reject(transaction.error);
      transaction.onerror = () => reject(transaction.error);
    });
  } finally {
    db.close();
  }
}

// IndexedDB stores structured clones, so the photo of an observation queued
// offline survives as a File. localStorage would JSON.stringify it into {}.
export function createIdbPersister(key) {
  return {
    persistClient: (client) =>
      withStore("readwrite", (store) => store.put(client, key)),
    restoreClient: () => withStore("readonly", (store) => store.get(key)),
    removeClient: () => withStore("readwrite", (store) => store.delete(key)),
  };
}
