// Mock the chrome extension APIs that aren't available in jsdom
const storage: Record<string, unknown> = {};

global.chrome = {
  identity: {
    getRedirectURL: () => "https://abcdefghijklmn.chromiumapp.org/",
    launchWebAuthFlow: vi.fn(),
  },
  storage: {
    local: {
      get: vi.fn(async (keys: string | string[]) => {
        const result: Record<string, unknown> = {};
        const keyList = Array.isArray(keys) ? keys : [keys];
        for (const k of keyList) {
          if (k in storage) result[k] = storage[k];
        }
        return result;
      }),
      set: vi.fn(async (items: Record<string, unknown>) => {
        Object.assign(storage, items);
      }),
      remove: vi.fn(async (keys: string | string[]) => {
        const keyList = Array.isArray(keys) ? keys : [keys];
        for (const k of keyList) delete storage[k];
      }),
    },
  },
} as unknown as typeof chrome;

// Reset storage between tests
beforeEach(() => {
  Object.keys(storage).forEach((k) => delete storage[k]);
  vi.clearAllMocks();
});
