import {refreshTokens, TokenPair} from "@/lib/auth/backend";
import "server-only";

// The backend rotates refresh tokens strictly: a refresh token can be used once, and using it a second
// time is treated as theft and revokes the whole session. Browsers routinely send several requests with
// the same (expired) access cookie at once, e.g. a navigation plus link prefetches, and requests sent
// shortly after a refresh may still carry the old cookie. So every request that presents the same refresh
// token shares one backend call and gets the same new pair, for a short window after it started.

const SHARE_RESULT_FOR_MS = 30_000;

type Entry = {result: Promise<TokenPair | null>; expiresAt: number};

const refreshes = new Map<string, Entry>();

/**
 * Resolves to the new token pair, or to null when the backend rejects the refresh token
 * (invalid, expired, reused or revoked). Rejects when the backend can't be reached or errors out.
 */
export function refreshSessionOnce(refreshToken: string): Promise<TokenPair | null> {
    const now = Date.now();
    for (const [token, entry] of refreshes) {
        if (entry.expiresAt <= now) {
            refreshes.delete(token);
        }
    }

    const existing = refreshes.get(refreshToken);
    if (existing) {
        return existing.result;
    }

    const result = refreshTokens(refreshToken);
    refreshes.set(refreshToken, {result, expiresAt: now + SHARE_RESULT_FOR_MS});
    // Don't keep transient failures around: the next request should retry
    result.catch(() => refreshes.delete(refreshToken));
    return result;
}
