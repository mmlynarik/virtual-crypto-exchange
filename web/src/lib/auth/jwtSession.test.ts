import {isAccessTokenUsable} from "@/lib/auth/jwtSession";
import {UnsecuredJWT} from "jose";
import {describe, expect, it} from "vitest";

const USER_ID = "019a0000-0000-7000-8000-0000000000aa";

// The web server never checks signatures (it doesn't hold the backend's secret), so unsigned tokens will do
function token(claims: Record<string, unknown>): string {
    const now = Math.floor(Date.now() / 1000);
    return new UnsecuredJWT({
        userId: USER_ID,
        type: "access",
        aud: "vce",
        iat: now,
        exp: now + 300,
        ...claims,
    }).encode();
}

describe("isAccessTokenUsable", () => {
    it("accepts an access token that isn't about to expire", () => {
        expect(isAccessTokenUsable(token({}))).toBe(true);
    });

    it("rejects a token that expires within the leeway", () => {
        expect(isAccessTokenUsable(token({exp: Math.floor(Date.now() / 1000) + 10}))).toBe(false);
    });

    it("rejects a refresh token", () => {
        expect(isAccessTokenUsable(token({type: "refresh"}))).toBe(false);
    });

    it("rejects a missing cookie and a value that isn't a JWT", () => {
        expect(isAccessTokenUsable(undefined)).toBe(false);
        expect(isAccessTokenUsable("not-a-jwt")).toBe(false);
    });
});
