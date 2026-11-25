import {BackendError, loginWithGithub} from "@/lib/auth/backend";
import {afterEach, beforeEach, describe, expect, it, vi} from "vitest";

const fetchMock = vi.fn<typeof fetch>();

beforeEach(() => {
    vi.stubGlobal("fetch", fetchMock);
});

afterEach(() => {
    vi.unstubAllGlobals();
    fetchMock.mockReset();
});

function respond(status: number, body: unknown) {
    const text = typeof body === "string" ? body : JSON.stringify(body);
    fetchMock.mockResolvedValueOnce(
        new Response(text, {status, headers: {"Content-Type": "application/json"}})
    );
}

describe("loginWithGithub", () => {
    it("posts the code and returns the token pair", async () => {
        respond(200, {access_token: "access", refresh_token: "refresh", token_type: "bearer"});

        const result = await loginWithGithub("gh-code");

        expect(result).toEqual({ok: true, tokens: {accessToken: "access", refreshToken: "refresh"}});
        const [url, init] = fetchMock.mock.calls[0];
        expect(url).toBe(`${process.env.BACKEND_API_URL}/auth/github`);
        expect(init?.method).toBe("POST");
        expect(JSON.parse(String(init?.body))).toEqual({code: "gh-code"});
    });

    it("reports a rejected GitHub login", async () => {
        respond(401, {detail: "GitHub authentication failed"});
        expect(await loginWithGithub("gh-code")).toEqual({ok: false, reason: "rejected"});
    });

    it("asks for the account's password when the email belongs to a password account", async () => {
        respond(409, {
            detail: {
                code: "ACCOUNT_EXISTS",
                message: "An account with this email already exists.",
                email: "alice@example.com",
                pending_link_token: "pending-token",
            },
        });
        expect(await loginWithGithub("gh-code")).toEqual({
            ok: false,
            reason: "link_required",
            email: "alice@example.com",
            pendingLinkToken: "pending-token",
        });
    });

    it.each([
        [
            "EMAIL_TAKEN",
            {detail: {code: "EMAIL_TAKEN", message: "An account with this GitHub email already exists."}},
        ],
        [
            "ACCOUNT_EXISTS without a token",
            {detail: {code: "ACCOUNT_EXISTS", message: "...", email: "a@b.c"}},
        ],
        ["an unknown code", {detail: {code: "SOMETHING_NEW", message: "..."}}],
        ["the old plain-string body", {detail: "An account with this GitHub email already exists"}],
        ["a body that isn't JSON", "Conflict"],
    ])("treats a 409 with %s as email taken", async (_, body) => {
        respond(409, body);
        expect(await loginWithGithub("gh-code")).toEqual({ok: false, reason: "email_taken"});
    });

    it("throws on other failures", async () => {
        respond(500, {detail: "Internal Server Error"});
        await expect(loginWithGithub("gh-code")).rejects.toBeInstanceOf(BackendError);
    });
});
