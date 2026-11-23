import {backendFetch} from "@/lib/backendApi";
import "server-only";
import {z} from "zod";

// GET /auth/me (UserPublic on the backend)
const currentUserSchema = z.object({
    id: z.string().uuid(),
    email: z.string().nullable(),
    github_id: z.number().nullable(),
    github_name: z.string().nullable(),
});

export type CurrentUser = z.infer<typeof currentUserSchema>;

/** The logged-in user. Logs the user out (via backendFetch) if the backend rejects the session. */
export async function getCurrentUser(): Promise<CurrentUser> {
    const res = await backendFetch("/auth/me");
    if (!res.ok) {
        throw new Error(`GET /auth/me failed with status ${res.status}`);
    }
    return currentUserSchema.parse(await res.json());
}

export function getDisplayName(user: CurrentUser): string {
    return user.github_name ?? user.email ?? "";
}
