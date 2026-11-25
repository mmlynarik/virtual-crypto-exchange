"use server";

import {linkGithubPending} from "@/lib/auth/backend";
import {clearPendingGithubLink, getPendingGithubLink} from "@/lib/auth/githubLink";
import {setSessionCookies} from "@/lib/auth/jwtSession";
import {redirect} from "next/navigation";
import {githubLinkSchema} from "../schemas/githubLink";

type FormState = {
    success: boolean;
    errors?: Record<string, string[]>;
};

/**
 * Confirms the password of the account that a GitHub login found by email, which links GitHub to it and
 * logs in. The pending link token stays in its httpOnly cookie; only the password comes from the form.
 */
export async function linkGithubAction(_: FormState, formData: FormData): Promise<FormState> {
    const parsed = githubLinkSchema.safeParse(Object.fromEntries(formData));
    if (!parsed.success) {
        return {success: false, errors: parsed.error.flatten().fieldErrors};
    }

    // Checked before calling the backend, which answers an expired token with the same 401 as a wrong password
    const link = await getPendingGithubLink();
    if (!link) {
        redirect("/login?error=github_link_expired");
    }

    const result = await linkGithubPending(link.token, parsed.data.password);
    if (result.ok) {
        await clearPendingGithubLink();
        await setSessionCookies(result.tokens);
        redirect("/home");
    }
    if (result.reason === "wrong_password") {
        // The pending link stays, so the user can try again
        return {success: false, errors: {root: ["Incorrect password"]}};
    }
    // already_linked: the account or the GitHub account got linked in the meantime
    await clearPendingGithubLink();
    redirect("/login?error=github_link_conflict");
}

export async function cancelGithubLink() {
    await clearPendingGithubLink();
    redirect("/login");
}
