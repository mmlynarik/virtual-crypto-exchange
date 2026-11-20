import {clearSessionCookies} from "@/lib/auth/jwtSession";
import {redirect} from "next/navigation";

// backendFetch() sends the user here when the backend rejects their access token. Server components can't
// change cookies, so they can't log the user out themselves, and just redirecting to /login would loop:
// the middleware only decodes the token, still sees a usable-looking cookie and sends the user to /home.
// The middleware doesn't run on /api/*, so this always gets through.
export async function GET() {
    await clearSessionCookies();
    redirect("/login");
}
