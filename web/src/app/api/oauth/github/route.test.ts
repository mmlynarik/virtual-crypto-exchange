import {GET} from "@/app/api/oauth/github/route";
import {loginWithGithub} from "@/lib/auth/backend";
import {setPendingGithubLink} from "@/lib/auth/githubLink";
import {setSessionCookies} from "@/lib/auth/jwtSession";
import {redirectedTo} from "@test/nextNavigation";
import {NextRequest} from "next/server";
import {beforeEach, describe, expect, it, vi} from "vitest";

vi.mock("next/navigation", () => import("@test/nextNavigation"));
vi.mock("@/lib/auth/backend", () => ({loginWithGithub: vi.fn()}));
vi.mock("@/lib/auth/githubLink", () => ({
    PENDING_GITHUB_LINK_PATH: "/link-github",
    setPendingGithubLink: vi.fn(),
}));
vi.mock("@/lib/auth/jwtSession", () => ({setSessionCookies: vi.fn()}));

beforeEach(() => {
    vi.clearAllMocks();
});

/** Calls the route and returns where it redirected to. */
function callback(query: string): Promise<string> {
    return redirectedTo(() => GET(new NextRequest(`http://localhost/api/oauth/github${query}`)));
}

const TOKENS = {accessToken: "access", refreshToken: "refresh"};

describe("GitHub OAuth callback", () => {
    it("goes back to login without a code (e.g. the user cancelled on GitHub)", async () => {
        expect(await callback("?error=access_denied")).toBe("/login");
        expect(loginWithGithub).not.toHaveBeenCalled();
    });

    it("logs in", async () => {
        vi.mocked(loginWithGithub).mockResolvedValue({ok: true, tokens: TOKENS});

        expect(await callback("?code=gh-code")).toBe("/home");
        expect(loginWithGithub).toHaveBeenCalledWith("gh-code");
        expect(setSessionCookies).toHaveBeenCalledWith(TOKENS);
    });

    it("keeps the pending link and asks for the account's password", async () => {
        vi.mocked(loginWithGithub).mockResolvedValue({
            ok: false,
            reason: "link_required",
            email: "alice@example.com",
            pendingLinkToken: "pending-token",
        });

        expect(await callback("?code=gh-code")).toBe("/link-github");
        expect(setPendingGithubLink).toHaveBeenCalledWith({
            email: "alice@example.com",
            token: "pending-token",
        });
        expect(setSessionCookies).not.toHaveBeenCalled();
    });

    it.each([
        ["email_taken", "/login?error=github_email_taken"],
        ["rejected", "/login?error=github_failed"],
    ] as const)("sends %s back to login with its message", async (reason, url) => {
        vi.mocked(loginWithGithub).mockResolvedValue({ok: false, reason});

        expect(await callback("?code=gh-code")).toBe(url);
        expect(setSessionCookies).not.toHaveBeenCalled();
        expect(setPendingGithubLink).not.toHaveBeenCalled();
    });
});
