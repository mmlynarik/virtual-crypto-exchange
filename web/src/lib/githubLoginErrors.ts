// Messages for the ?error= that a GitHub login or a GitHub link sends back to /login with. A Map, not an
// object literal, so a code like "toString" doesn't find an inherited property.
const GITHUB_LOGIN_ERRORS = new Map<string, string>([
    ["github_failed", "GitHub login failed. Please try again."],
    [
        "github_email_taken",
        "An account with your GitHub email already exists and is connected to a different GitHub account.",
    ],
    ["github_link_expired", "Connecting GitHub took too long. Log in with GitHub again to retry."],
    [
        "github_link_conflict",
        "This account or this GitHub account is already connected. Try logging in with GitHub or your password.",
    ],
]);

export function githubLoginErrorMessage(error: string | undefined): string | undefined {
    return error ? GITHUB_LOGIN_ERRORS.get(error) : undefined;
}
