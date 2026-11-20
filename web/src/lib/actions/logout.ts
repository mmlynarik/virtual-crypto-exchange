"use server";

import {logoutSession} from "@/lib/auth/backend";
import {clearSessionCookies, REFRESH_COOKIE} from "@/lib/auth/jwtSession";
import {cookies} from "next/headers";
import {redirect} from "next/navigation";

export async function logout() {
    const refreshToken = (await cookies()).get(REFRESH_COOKIE)?.value;
    if (refreshToken) {
        try {
            // Revoke the session on the backend so the refresh token can't be used anymore
            await logoutSession(refreshToken);
        } catch (e) {
            // Still log the user out locally; the token expires on its own
            console.error("Backend logout failed", e);
        }
    }
    await clearSessionCookies();
    redirect("/login");
}
