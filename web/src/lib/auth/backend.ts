import {BACKEND_API_URL} from "@/config";
import "server-only";
import {z} from "zod";

// Client for the FastAPI /auth/* endpoints. The backend is the auth authority: it checks passwords,
// exchanges GitHub codes and issues/rotates the JWT pair; the web server only stores it in cookies.

const tokenPairResponseSchema = z.object({
    access_token: z.string(),
    refresh_token: z.string(),
});

const validationErrorSchema = z.object({
    detail: z.array(z.object({loc: z.array(z.union([z.string(), z.number()])), msg: z.string()})),
});

export type TokenPair = {
    accessToken: string;
    refreshToken: string;
};

export type FieldErrors = Record<string, string[]>;

export type RegisterResult =
    | {ok: true; tokens: TokenPair}
    | {ok: false; reason: "email_taken"}
    | {ok: false; reason: "invalid"; errors: FieldErrors};

export type GithubLoginResult =
    | {ok: true; tokens: TokenPair}
    | {ok: false; reason: "rejected"} // bad code, or the GitHub account has no verified primary email
    | {ok: false; reason: "email_taken"}; // the GitHub email already belongs to another account

export class BackendError extends Error {
    constructor(path: string, status: number) {
        super(`Backend request to ${path} failed with status ${status}`);
        this.name = "BackendError";
    }
}

async function post(path: string, body: unknown): Promise<Response> {
    if (!BACKEND_API_URL) {
        throw new Error("Missing BACKEND_API_URL env variable");
    }
    return fetch(`${BACKEND_API_URL}${path}`, {
        method: "POST",
        body: JSON.stringify(body),
        headers: {"Content-Type": "application/json", Accept: "application/json"},
        cache: "no-store",
    });
}

async function parseTokenPair(res: Response): Promise<TokenPair> {
    const data = tokenPairResponseSchema.parse(await res.json());
    return {accessToken: data.access_token, refreshToken: data.refresh_token};
}

/** Returns null when the backend rejects the credentials/token (401); throws on any other failure. */
async function postForTokenPair(path: string, body: unknown): Promise<TokenPair | null> {
    const res = await post(path, body);
    if (res.status === 401) {
        return null;
    }
    if (!res.ok) {
        throw new BackendError(path, res.status);
    }
    return parseTokenPair(res);
}

export async function loginWithPassword(email: string, password: string): Promise<TokenPair | null> {
    return postForTokenPair("/auth/login", {email, password});
}

export async function loginWithGithub(code: string): Promise<GithubLoginResult> {
    const path = "/auth/github";
    const res = await post(path, {code});
    if (res.status === 401) {
        return {ok: false, reason: "rejected"};
    }
    if (res.status === 409) {
        return {ok: false, reason: "email_taken"};
    }
    if (!res.ok) {
        throw new BackendError(path, res.status);
    }
    return {ok: true, tokens: await parseTokenPair(res)};
}

/** Rotates the refresh token. The old one is single-use: sending it again revokes the whole session. */
export async function refreshTokens(refreshToken: string): Promise<TokenPair | null> {
    return postForTokenPair("/auth/refresh", {refresh_token: refreshToken});
}

export async function registerWithPassword(email: string, password: string): Promise<RegisterResult> {
    const path = "/auth/register";
    const res = await post(path, {email, password});
    if (res.status === 409) {
        return {ok: false, reason: "email_taken"};
    }
    if (res.status === 422) {
        return {ok: false, reason: "invalid", errors: toFieldErrors(await res.json())};
    }
    if (!res.ok) {
        throw new BackendError(path, res.status);
    }
    return {ok: true, tokens: await parseTokenPair(res)};
}

const emailAvailabilitySchema = z.object({available: z.boolean()});

/**
 * For the sign-up form's live check. Returns true when the backend can't answer (e.g. a malformed email,
 * which the form reports itself), so it never shows "Email is already in use" wrongly; /auth/register
 * still rejects a taken email.
 */
export async function isEmailAvailable(email: string): Promise<boolean> {
    if (!BACKEND_API_URL) {
        throw new Error("Missing BACKEND_API_URL env variable");
    }
    const query = new URLSearchParams({email});
    const res = await fetch(`${BACKEND_API_URL}/auth/email-available?${query}`, {cache: "no-store"});
    if (!res.ok) {
        return true;
    }
    return emailAvailabilitySchema.parse(await res.json()).available;
}

/** Revokes the session (refresh token family). Idempotent on the backend. */
export async function logoutSession(refreshToken: string): Promise<void> {
    const path = "/auth/logout";
    const res = await post(path, {refresh_token: refreshToken});
    if (!res.ok) {
        throw new BackendError(path, res.status);
    }
}

// FastAPI 422 body: {detail: [{loc: ["body", "email"], msg: "..."}]}
function toFieldErrors(body: unknown): FieldErrors {
    const parsed = validationErrorSchema.safeParse(body);
    if (!parsed.success) {
        return {root: ["Invalid sign up data"]};
    }
    const errors: FieldErrors = {};
    for (const {loc, msg} of parsed.data.detail) {
        const field = loc.length > 1 ? String(loc[loc.length - 1]) : "root";
        (errors[field] ??= []).push(msg);
    }
    return errors;
}
