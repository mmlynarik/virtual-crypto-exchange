import {BACKEND_API_URL} from "@/config";
import {ACCESS_COOKIE} from "@/lib/auth/jwtSession";
import {cookies} from "next/headers";
import {redirect} from "next/navigation";
import "server-only";

// Clears the session cookies and goes to /login; see app/api/auth/session-expired/route.ts
export const SESSION_EXPIRED_PATH = "/api/auth/session-expired";

/**
 * fetch() against the backend as the logged-in user, sending the access token as a bearer token.
 * Use it from server components, server actions and route handlers for anything that needs the user.
 *
 * The middleware has already refreshed the access token for this request if needed, so a 401 means the
 * backend won't accept this session at all (revoked, user deleted, or a cookie that only looked valid to
 * the web server). The user is then logged out via SESSION_EXPIRED_PATH.
 *
 * redirect() works by throwing, so don't call this inside a try/catch that swallows errors.
 */
export async function backendFetch(path: string, init: RequestInit = {}): Promise<Response> {
    if (!BACKEND_API_URL) {
        throw new Error("Missing BACKEND_API_URL env variable");
    }
    const accessToken = (await cookies()).get(ACCESS_COOKIE)?.value;
    if (!accessToken) {
        redirect(SESSION_EXPIRED_PATH);
    }

    const headers = new Headers(init.headers);
    headers.set("Authorization", `Bearer ${accessToken}`);
    const res = await fetch(`${BACKEND_API_URL}${path}`, {cache: "no-store", ...init, headers});
    if (res.status === 401) {
        redirect(SESSION_EXPIRED_PATH);
    }
    return res;
}
