import { describe, it, expect, vi } from "vitest";
import { signIn, getSession, signOut } from "../auth";

describe("signIn", () => {
  it("extracts session_id from URL fragment and stores it", async () => {
    const fakeSessionId = "abc-session-123";
    vi.mocked(chrome.identity.launchWebAuthFlow).mockResolvedValue(
      `https://abcdefghijklmn.chromiumapp.org/#session_id=${fakeSessionId}`
    );

    const result = await signIn();

    expect(result).toBe(fakeSessionId);
    expect(chrome.storage.local.set).toHaveBeenCalledWith({ sessionId: fakeSessionId });
  });

  it("throws if launchWebAuthFlow returns nothing", async () => {
    vi.mocked(chrome.identity.launchWebAuthFlow).mockResolvedValue(undefined);
    await expect(signIn()).rejects.toThrow("cancelled");
  });

  it("throws if no session_id in the redirect URL", async () => {
    vi.mocked(chrome.identity.launchWebAuthFlow).mockResolvedValue(
      "https://abcdefghijklmn.chromiumapp.org/#error=access_denied"
    );
    await expect(signIn()).rejects.toThrow("No session");
  });
});

describe("getSession", () => {
  it("returns null when no session stored", async () => {
    const result = await getSession();
    expect(result).toBeNull();
  });

  it("returns stored session_id", async () => {
    await chrome.storage.local.set({ sessionId: "stored-session" });
    const result = await getSession();
    expect(result).toBe("stored-session");
  });
});

describe("signOut", () => {
  it("removes sessionId from storage", async () => {
    await chrome.storage.local.set({ sessionId: "to-remove" });
    await signOut();
    expect(chrome.storage.local.remove).toHaveBeenCalledWith("sessionId");
  });
});
