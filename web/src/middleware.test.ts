import {middleware} from "@/middleware";
import {UnsecuredJWT} from "jose";
import {NextRequest} from "next/server";
import {describe, expect, it, vi} from "vitest";

// No test here presents a refresh token, so the backend is never asked to refresh
vi.mock("@/lib/auth/refresh", () => ({refreshSessionOnce: vi.fn()}));

// The middleware never checks signatures (it doesn't hold the backend's secret), so an unsigned token will do
function accessToken(): string {
    const now = Math.floor(Date.now() / 1000);
    return new UnsecuredJWT({
        userId: "019a0000-0000-7000-8000-0000000000aa",
        type: "access",
        aud: "vce",
        iat: now,
        exp: now + 300,
    }).encode();
}

/** Where the middleware sends the request: the redirect target, or "next" when it lets it through. */
async function route(path: string, {loggedIn}: {loggedIn: boolean}): Promise<string> {
    const headers = loggedIn ? {cookie: `access=${accessToken()}`} : undefined;
    const res = await middleware(new NextRequest(`http://localhost${path}`, {headers}));
    const location = res.headers.get("location");
    return location ? new URL(location).pathname : "next";
}

describe("middleware", () => {
    it("lets a logged-out user open the GitHub link page", async () => {
        expect(await route("/link-github", {loggedIn: false})).toBe("next");
    });

    it("sends a logged-in user from the GitHub link page home, like from login", async () => {
        expect(await route("/link-github", {loggedIn: true})).toBe("/home");
        expect(await route("/login", {loggedIn: true})).toBe("/home");
    });

    it("still sends a logged-out user from private pages to login", async () => {
        expect(await route("/home", {loggedIn: false})).toBe("/login");
        expect(await route("/login", {loggedIn: false})).toBe("next");
    });
});
