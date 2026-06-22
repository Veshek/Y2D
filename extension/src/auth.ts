// OAuth from the extension's side. We never touch Google tokens here — the backend
// holds those. launchWebAuthFlow opens the backend's /auth/login, the backend
// completes the dance server-side, then redirects back to this extension's
// chromiumapp.org URL carrying only an opaque session_id.

const BACKEND = "http://localhost:8000";

export async function signIn(): Promise<string> {
  const redirectUri = chrome.identity.getRedirectURL(); // https://<id>.chromiumapp.org/
  const authUrl =
    `${BACKEND}/auth/login?ext_redirect=${encodeURIComponent(redirectUri)}`;

  const resultUrl = await chrome.identity.launchWebAuthFlow({
    url: authUrl,
    interactive: true,
  });
  if (!resultUrl) throw new Error("Sign-in was cancelled");

  // session_id comes back in the URL fragment.
  const fragment = new URL(resultUrl).hash.slice(1);
  const sessionId = new URLSearchParams(fragment).get("session_id");
  if (!sessionId) throw new Error("No session returned from backend");

  await chrome.storage.local.set({ sessionId });
  return sessionId;
}

export async function getSession(): Promise<string | null> {
  const { sessionId } = await chrome.storage.local.get("sessionId");
  return sessionId ?? null;
}

export async function signOut(): Promise<void> {
  await chrome.storage.local.remove("sessionId");
}
