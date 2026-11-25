import {githubLoginErrorMessage} from "@/lib/githubLoginErrors";
import {describe, expect, it} from "vitest";

describe("githubLoginErrorMessage", () => {
    // Every ?error= the app sends to /login: the GitHub callback route, and the link page and its actions
    it.each(["github_failed", "github_email_taken", "github_link_expired", "github_link_conflict"])(
        "has a message for %s",
        (error) => {
            expect(githubLoginErrorMessage(error)).toBeTruthy();
        }
    );

    it("no longer points to account settings, which don't exist", () => {
        expect(githubLoginErrorMessage("github_email_taken")).not.toMatch(/settings/i);
    });

    it("tells the user to retry with GitHub when linking took too long", () => {
        expect(githubLoginErrorMessage("github_link_expired")).toMatch(/GitHub again/);
    });

    it("shows nothing for no error or an unknown one", () => {
        expect(githubLoginErrorMessage(undefined)).toBeUndefined();
        expect(githubLoginErrorMessage("something_else")).toBeUndefined();
        expect(githubLoginErrorMessage("toString")).toBeUndefined();
    });
});
