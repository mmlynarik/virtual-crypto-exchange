import {
    clearPendingGithubLink,
    getPendingGithubLink,
    PENDING_GITHUB_LINK_COOKIE,
    PENDING_GITHUB_LINK_PATH,
    setPendingGithubLink,
} from "@/lib/auth/githubLink";
import {UnsecuredJWT} from "jose";
import {beforeEach, describe, expect, it, vi} from "vitest";

// In-memory stand-in for the cookie store that next/headers' cookies() returns
const cookieStore = vi.hoisted(() => {
    const values = new Map<string, string>();
    return {
        values,
        get: vi.fn((name: string) => (values.has(name) ? {name, value: values.get(name)!} : undefined)),
        set: vi.fn<(name: string, value: string, options: Record<string, unknown>) => void>(
            (name, value) => void values.set(name, value)
        ),
        delete: vi.fn((options: {name: string}) => void values.delete(options.name)),
    };
});

vi.mock("next/headers", () => ({cookies: async () => cookieStore}));

beforeEach(() => {
    cookieStore.values.clear();
    vi.clearAllMocks();
});

const now = () => Math.floor(Date.now() / 1000);

// The web server never checks signatures (it doesn't hold the backend's secret), so unsigned tokens will do
function pendingLinkToken(claims: Record<string, unknown> = {}): string {
    return new UnsecuredJWT({
        userId: "019a0000-0000-7000-8000-0000000000aa",
        githubId: 12345678,
        type: "github_pending_link",
        aud: "vce",
        iat: now(),
        exp: now() + 600,
        ...claims,
    }).encode();
}

describe("pending GitHub link cookie", () => {
    it("round-trips the email and token", async () => {
        const token = pendingLinkToken();
        await setPendingGithubLink({email: "alice@example.com", token});
        expect(await getPendingGithubLink()).toEqual({email: "alice@example.com", token});
    });

    it("is httpOnly, scoped to the link page and expires with the token", async () => {
        const exp = now() + 600;
        await setPendingGithubLink({email: "alice@example.com", token: pendingLinkToken({exp})});

        const [name, , options] = cookieStore.set.mock.calls[0];
        expect(name).toBe(PENDING_GITHUB_LINK_COOKIE);
        expect(options).toMatchObject({httpOnly: true, sameSite: "lax", path: PENDING_GITHUB_LINK_PATH});
        expect(options.expires).toEqual(new Date(exp * 1000));
    });

    it("refuses to store a token that isn't a pending link token", async () => {
        await expect(
            setPendingGithubLink({email: "alice@example.com", token: pendingLinkToken({type: "access"})})
        ).rejects.toThrow();
        expect(cookieStore.set).not.toHaveBeenCalled();
    });

    it.each([
        ["no cookie", undefined],
        ["a value that isn't JSON", "not json"],
        ["JSON of the wrong shape", JSON.stringify({email: "alice@example.com"})],
        ["a token that isn't a JWT", JSON.stringify({email: "alice@example.com", token: "not-a-jwt"})],
        [
            "an access token",
            JSON.stringify({email: "alice@example.com", token: pendingLinkToken({type: "access"})}),
        ],
        [
            "an expired token",
            JSON.stringify({email: "alice@example.com", token: pendingLinkToken({exp: now() - 1})}),
        ],
        [
            "a token about to expire",
            JSON.stringify({email: "alice@example.com", token: pendingLinkToken({exp: now() + 5})}),
        ],
    ])("reads %s as no pending link", async (_, value) => {
        if (value !== undefined) {
            cookieStore.values.set(PENDING_GITHUB_LINK_COOKIE, value);
        }
        expect(await getPendingGithubLink()).toBeNull();
    });

    it("is cleared on its own path", async () => {
        await setPendingGithubLink({email: "alice@example.com", token: pendingLinkToken()});
        await clearPendingGithubLink();

        expect(cookieStore.delete).toHaveBeenCalledWith({
            name: PENDING_GITHUB_LINK_COOKIE,
            path: PENDING_GITHUB_LINK_PATH,
        });
        expect(await getPendingGithubLink()).toBeNull();
    });
});
