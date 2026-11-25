import {TokenPair} from "@/lib/auth/backend";
import {accessTokenSchema} from "@/lib/schemas/jwt";
import {decodeJwt} from "jose";
import {cookies} from "next/headers";
import "server-only";

export const ACCESS_COOKIE = "access";
export const REFRESH_COOKIE = "refresh";

// Treat backend tokens as expired a little early, so one that passes here is still valid when the backend
// checks it (request latency, clock skew between containers)
export const EXPIRY_LEEWAY_SECONDS = 30;

type SessionCookie = {
    name: string;
    value: string;
    options: {httpOnly: boolean; sameSite: "lax"; path: string; expires: Date};
};

/**
 * Whether the access token looks usable: an access token with the expected claims that isn't (about to be)
 * expired. The signature is NOT checked, since web doesn't hold the backend's signing secret. This only
 * drives routing and refresh timing; the backend verifies the token on every API call (see backendApi.ts),
 * so a forged cookie gets past the redirect but never gets any data.
 */
export function isAccessTokenUsable(token: string | undefined): boolean {
    if (!token) {
        return false;
    }
    let claims;
    try {
        claims = accessTokenSchema.safeParse(decodeJwt(token));
    } catch {
        // Not a JWT
        return false;
    }
    return claims.success && claims.data.exp - EXPIRY_LEEWAY_SECONDS > Date.now() / 1000;
}

function getTokenExpiryDate(token: string): Date {
    const {exp} = decodeJwt(token);
    if (!exp) {
        throw new Error("Token has no exp claim");
    }
    return new Date(exp * 1000);
}

/** Cookies holding the token pair; each cookie expires together with its token. */
export function getSessionCookies(tokens: TokenPair): SessionCookie[] {
    return [
        {name: ACCESS_COOKIE, value: tokens.accessToken},
        {name: REFRESH_COOKIE, value: tokens.refreshToken},
    ].map(({name, value}) => ({
        name,
        value,
        options: {
            httpOnly: true,
            // secure: true,
            sameSite: "lax",
            path: "/",
            expires: getTokenExpiryDate(value),
        },
    }));
}

/** For server actions and route handlers. The middleware sets cookies on its NextResponse instead. */
export async function setSessionCookies(tokens: TokenPair) {
    const cookieStore = await cookies();
    for (const {name, value, options} of getSessionCookies(tokens)) {
        cookieStore.set(name, value, options);
    }
}

export async function clearSessionCookies() {
    const cookieStore = await cookies();
    cookieStore.delete(ACCESS_COOKIE);
    cookieStore.delete(REFRESH_COOKIE);
}
