import {loginWithGithub} from "@/lib/auth/backend";
import {PENDING_GITHUB_LINK_PATH, setPendingGithubLink} from "@/lib/auth/githubLink";
import {setSessionCookies} from "@/lib/auth/jwtSession";
import {redirect} from "next/navigation";
import {type NextRequest} from "next/server";

// GitHub redirects here after the user authorizes the app. The backend exchanges the code for a GitHub
// token, finds or creates the user, and returns our JWT pair. When the GitHub email belongs to a password
// account, the user confirms that account's password on the link page instead.
export async function GET(request: NextRequest) {
    const code = request.nextUrl.searchParams.get("code");
    if (!code) {
        // e.g. ?error=access_denied when the user cancels on GitHub
        redirect("/login");
    }

    const result = await loginWithGithub(code);
    if (!result.ok && result.reason === "link_required") {
        await setPendingGithubLink({email: result.email, token: result.pendingLinkToken});
        redirect(PENDING_GITHUB_LINK_PATH);
    }
    if (!result.ok) {
        console.log(`GitHub login rejected by backend: ${result.reason}`);
        redirect(`/login?error=${result.reason === "email_taken" ? "github_email_taken" : "github_failed"}`);
    }

    await setSessionCookies(result.tokens);
    redirect("/home");
}
