import {cancelGithubLink, linkGithubAction} from "@/lib/actions/githubLink";
import {linkGithubPending} from "@/lib/auth/backend";
import {clearPendingGithubLink, getPendingGithubLink} from "@/lib/auth/githubLink";
import {setSessionCookies} from "@/lib/auth/jwtSession";
import {redirectedTo} from "@test/nextNavigation";
import {beforeEach, describe, expect, it, vi} from "vitest";

vi.mock("next/navigation", () => import("@test/nextNavigation"));
vi.mock("@/lib/auth/backend", () => ({linkGithubPending: vi.fn()}));
vi.mock("@/lib/auth/githubLink", () => ({
    getPendingGithubLink: vi.fn(),
    clearPendingGithubLink: vi.fn(),
}));
vi.mock("@/lib/auth/jwtSession", () => ({setSessionCookies: vi.fn()}));

const LINK = {email: "alice@example.com", token: "pending-token"};
const TOKENS = {accessToken: "access", refreshToken: "refresh"};

beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(getPendingGithubLink).mockResolvedValue(LINK);
});

function submit(password: string) {
    const formData = new FormData();
    formData.set("password", password);
    return linkGithubAction({success: false}, formData);
}

describe("linkGithubAction", () => {
    it("links GitHub, logs in and goes home", async () => {
        vi.mocked(linkGithubPending).mockResolvedValue({ok: true, tokens: TOKENS});

        expect(await redirectedTo(() => submit("correct horse"))).toBe("/home");
        expect(linkGithubPending).toHaveBeenCalledWith("pending-token", "correct horse");
        expect(clearPendingGithubLink).toHaveBeenCalled();
        expect(setSessionCookies).toHaveBeenCalledWith(TOKENS);
    });

    it("asks again after a wrong password, keeping the pending link", async () => {
        vi.mocked(linkGithubPending).mockResolvedValue({ok: false, reason: "wrong_password"});

        expect(await submit("wrong")).toEqual({success: false, errors: {root: ["Incorrect password"]}});
        expect(clearPendingGithubLink).not.toHaveBeenCalled();
        expect(setSessionCookies).not.toHaveBeenCalled();
    });

    it("requires a password without calling the backend", async () => {
        const state = await submit("");
        expect(state.success).toBe(false);
        expect(state.errors?.password).toBeDefined();
        expect(linkGithubPending).not.toHaveBeenCalled();
    });

    it("sends an expired or missing pending link back to login", async () => {
        vi.mocked(getPendingGithubLink).mockResolvedValue(null);

        expect(await redirectedTo(() => submit("correct horse"))).toBe("/login?error=github_link_expired");
        expect(linkGithubPending).not.toHaveBeenCalled();
    });

    it("sends a link made meanwhile back to login and drops the pending link", async () => {
        vi.mocked(linkGithubPending).mockResolvedValue({ok: false, reason: "already_linked"});

        expect(await redirectedTo(() => submit("correct horse"))).toBe("/login?error=github_link_conflict");
        expect(clearPendingGithubLink).toHaveBeenCalled();
        expect(setSessionCookies).not.toHaveBeenCalled();
    });
});

describe("cancelGithubLink", () => {
    it("drops the pending link and goes back to login", async () => {
        expect(await redirectedTo(() => cancelGithubLink())).toBe("/login");
        expect(clearPendingGithubLink).toHaveBeenCalled();
    });
});
