const DB_NAME = 'drone_sim_config';
const DB_VERSION = 1;
const STORE_NAME = 'loaded_config';
const CONFIG_KEY = 'current';

function _openDB() {
  return new Promise((resolve, reject) => {
    const request = indexedDB.open(DB_NAME, DB_VERSION);
    request.onupgradeneeded = () => {
      const db = request.result;
      if (!db.objectStoreNames.contains(STORE_NAME)) {
        db.createObjectStore(STORE_NAME);
      }
    };
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error);
  });
}

/**
 * Save a loaded config (JSON + image blobs) to IndexedDB.
 * @param {object} config  - The parsed config.json object
 * @param {Blob}   mapBlob - The map image blob
 * @param {Blob}   droneBlob - The drone image blob
 */
export async function saveLoadedConfig(config, mapBlob, droneBlob) {
  const db = await _openDB();
  return new Promise((resolve, reject) => {
    const tx = db.transaction(STORE_NAME, 'readwrite');
    tx.objectStore(STORE_NAME).put({ config, mapBlob, droneBlob }, CONFIG_KEY);
    tx.oncomplete = () => { db.close(); resolve(); };
    tx.onerror = () => { db.close(); reject(tx.error); };
  });
}

/**
 * Get the loaded config from IndexedDB.
 * @returns {Promise<{config: object, mapBlobURL: string, droneBlobURL: string} | null>}
 */
export async function getLoadedConfig() {
  const db = await _openDB();
  return new Promise((resolve, reject) => {
    const tx = db.transaction(STORE_NAME, 'readonly');
    const req = tx.objectStore(STORE_NAME).get(CONFIG_KEY);
    req.onsuccess = () => {
      db.close();
      const data = req.result;
      if (!data) { resolve(null); return; }
      const mapBlobURL = URL.createObjectURL(data.mapBlob);
      const droneBlobURL = URL.createObjectURL(data.droneBlob);
      resolve({ config: data.config, mapBlobURL, droneBlobURL });
    };
    req.onerror = () => { db.close(); reject(req.error); };
  });
}

/**
 * Clear the loaded config from IndexedDB.
 */
export async function clearLoadedConfig() {
  const db = await _openDB();
  return new Promise((resolve, reject) => {
    const tx = db.transaction(STORE_NAME, 'readwrite');
    tx.objectStore(STORE_NAME).delete(CONFIG_KEY);
    tx.oncomplete = () => { db.close(); resolve(); };
    tx.onerror = () => { db.close(); reject(tx.error); };
  });
}
