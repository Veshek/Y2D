import { describe, it, expect, vi, beforeEach } from "vitest";
import { getMe, createTransfers } from "../api";

const SESSION = "test-session-id";

function mockFetch(data: unknown, ok = true, status = 200) {
  return vi.spyOn(global, "fetch").mockResolvedValue({
    ok,
    status,
    json: async () => data,
  } as Response);
}

describe("getMe", () => {
  it("sends X-Session-Id header and returns email", async () => {
    const spy = mockFetch({ email: "user@example.com" });
    const result = await getMe(SESSION);
    expect(result.email).toBe("user@example.com");
    expect(spy).toHaveBeenCalledWith(
      expect.stringContaining("/me"),
      expect.objectContaining({
        headers: expect.objectContaining({ "X-Session-Id": SESSION }),
      })
    );
  });

  it("throws on non-ok response", async () => {
    mockFetch({}, false, 401);
    await expect(getMe(SESSION)).rejects.toThrow();
  });
});

describe("createTransfers", () => {
  it("posts items and returns transfer_ids", async () => {
    const spy = mockFetch({ transfer_ids: ["t1", "t2"] });
    const result = await createTransfers(SESSION, [
      { file_id: "f1", privacy: "private" },
      { file_id: "f2", privacy: "public", title: "My Video" },
    ]);
    expect(result.transfer_ids).toEqual(["t1", "t2"]);
    expect(spy).toHaveBeenCalledWith(
      expect.stringContaining("/transfers"),
      expect.objectContaining({ method: "POST" })
    );
  });

  it("throws on backend error", async () => {
    mockFetch({}, false, 500);
    await expect(
      createTransfers(SESSION, [{ file_id: "f1", privacy: "private" }])
    ).rejects.toThrow();
  });
});
