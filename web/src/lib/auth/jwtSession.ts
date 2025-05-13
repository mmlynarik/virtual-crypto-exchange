import {
    JWT_ACCESS_TOKEN_EXPIRY_SECONDS,
    JWT_AUDIENCE,
    JWT_REFRESH_TOKEN_EXPIRY_SECONDS,
    JWT_SECRET_KEY,
} from "@/config";
import {JWTPrivateClaims, jwtSchema} from "@/lib/schemas/jwt";
import {JWTPayload, SignJWT, jwtVerify} from "jose";
import {cookies} from "next/headers";
import {NextRequest} from "next/server";
import "server-only";

const JWT_SECRET_KEY_ENCODED = new TextEncoder().encode(JWT_SECRET_KEY);

export async function getSignedJWT(payload: JWTPrivateClaims, expiresAt: Date) {
    return new SignJWT(payload)
        .setProtectedHeader({alg: "HS256"})
        .setIssuedAt()
        .setExpirationTime(expiresAt)
        .setAudience(JWT_AUDIENCE)
        .sign(JWT_SECRET_KEY_ENCODED);
}

export async function verifyJWT(token: string) {
    try {
        return (await jwtVerify(token, JWT_SECRET_KEY_ENCODED, {algorithms: ["HS256"]})).payload;
    } catch (e) {
        console.log(e);
        return null;
    }
}

export async function validateJWT(payload: JWTPayload) {
    return await jwtSchema.safeParseAsync(payload);
}

export async function refreshAccessToken(req: NextRequest, currentRefreshToken: string | undefined) {
    const res = await fetch(`http://${req.nextUrl.host}/api/token/refresh`, {
        method: "POST",
        body: JSON.stringify({refreshToken: currentRefreshToken}),
        headers: {Accept: "application/json"},
    });
    if (!res.ok) {
        return false;
    }
    const {accessToken, refreshToken} = await res.json();
    setJWTSessionHeader(accessToken, refreshToken);
    console.log(`Access token ${refreshToken ? "and refresh token " : ""}refreshed`);
    return true;
}

export async function IsTokenOK(token: string | undefined): Promise<boolean> {
    if (!token) {
        return false;
    }
    const payload = await verifyJWT(token);
    if (!payload) {
        return false;
    }
    return (await validateJWT(payload)).success;
}

export async function isAuthenticated(
    req: NextRequest,
    accessToken: string | undefined,
    refreshToken: string | undefined
) {
    const accessTokenOk = await IsTokenOK(accessToken);
    if (accessTokenOk) {
        return true;
    }
    return await refreshAccessToken(req, refreshToken);
}

export async function createJWTSession(userId: number) {
    const accessTokenExpiryDate = getTokenExpiryDate(JWT_ACCESS_TOKEN_EXPIRY_SECONDS);
    const refreshTokenExpiryDate = getTokenExpiryDate(JWT_REFRESH_TOKEN_EXPIRY_SECONDS);

    const accessToken = await getSignedJWT({userId}, accessTokenExpiryDate);
    const refreshToken = await getSignedJWT({userId}, refreshTokenExpiryDate);

    return {accessToken, refreshToken};
}

export async function setJWTSessionHeader(access_token: string, refresh_token: string | null = null) {
    const cookieStore = await cookies();
    cookieStore.set("access", access_token, {
        httpOnly: true,
        // secure: true,
        expires: getTokenExpiryDate(JWT_ACCESS_TOKEN_EXPIRY_SECONDS),
        sameSite: "lax",
        path: "/",
    });
    if (refresh_token) {
        cookieStore.set("refresh", refresh_token, {
            httpOnly: true,
            // secure: true,
            expires: getTokenExpiryDate(JWT_REFRESH_TOKEN_EXPIRY_SECONDS),
            sameSite: "lax",
            path: "/",
        });
    }
}

function getTokenExpiryDate(expiration_seconds: number) {
    return new Date(Date.now() + expiration_seconds * 1000);
}

export async function deleteJWTSession() {
    const cookieStore = await cookies();
    cookieStore.delete("access");
    cookieStore.delete("refresh");
}
