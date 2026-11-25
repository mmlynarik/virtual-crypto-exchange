import {EXPIRY_LEEWAY_SECONDS} from "@/lib/auth/jwtSession";
import {githubPendingLinkTokenSchema} from "@/lib/schemas/jwt";
import {decodeJwt} from "jose";
import {cookies} from "next/headers";
import "server-only";
import {z} from "zod";

// Between a GitHub login that answered link_required and the password confirmation on the link page, the
// pending link token and the email it was issued for live in this cookie. httpOnly, so client JavaScript
// never sees the token, and scoped to the link page, so the browser sends it nowhere else.
export const PENDING_GITHUB_LINK_COOKIE = "github_pending_link";
export const PENDING_GITHUB_LINK_PATH = "/link-github";

const pendingGithubLinkSchema = z.object({email: z.string(), token: z.string()});

export type PendingGithubLink = z.infer<typeof pendingGithubLinkSchema>;

/**
 * The token's expiry (seconds since the epoch), or null when it isn't a pending link token. The signature
 * is NOT checked, since web doesn't hold the backend's signing secret; the backend verifies the token.
 */
function getPendingLinkTokenExpiry(token: string): number | null {
    try {
        const claims = githubPendingLinkTokenSchema.safeParse(decodeJwt(token));
        return claims.success ? claims.data.exp : null;
    } catch {
        // Not a JWT
        return null;
    }
}

/** For the GitHub callback route. The cookie expires together with the token. */
export async function setPendingGithubLink(link: PendingGithubLink) {
    const exp = getPendingLinkTokenExpiry(link.token);
    if (exp === null) {
        throw new Error("Not a GitHub pending link token");
    }
    (await cookies()).set(PENDING_GITHUB_LINK_COOKIE, JSON.stringify(link), {
        httpOnly: true,
        // secure: true,
        sameSite: "lax",
        path: PENDING_GITHUB_LINK_PATH,
        expires: new Date(exp * 1000),
    });
}

/**
 * The pending link, or null when there is none to use: no cookie, a malformed one, or a token that is
 * expired or about to expire. Checking expiry here is what tells an expired token apart from a wrong
 * password, which the backend both answers with 401.
 */
export async function getPendingGithubLink(): Promise<PendingGithubLink | null> {
    const value = (await cookies()).get(PENDING_GITHUB_LINK_COOKIE)?.value;
    if (!value) {
        return null;
    }
    let link;
    try {
        link = pendingGithubLinkSchema.safeParse(JSON.parse(value));
    } catch {
        // Not JSON
        return null;
    }
    if (!link.success) {
        return null;
    }
    const exp = getPendingLinkTokenExpiry(link.data.token);
    if (exp === null || exp - EXPIRY_LEEWAY_SECONDS <= Date.now() / 1000) {
        return null;
    }
    return link.data;
}

export async function clearPendingGithubLink() {
    // A cookie set on a path is only removed by a deletion on that same path
    (await cookies()).delete({name: PENDING_GITHUB_LINK_COOKIE, path: PENDING_GITHUB_LINK_PATH});
}
