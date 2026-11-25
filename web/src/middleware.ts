import {TokenPair} from "@/lib/auth/backend";
import {PENDING_GITHUB_LINK_PATH} from "@/lib/auth/githubLink";
import {ACCESS_COOKIE, getSessionCookies, isAccessTokenUsable, REFRESH_COOKIE} from "@/lib/auth/jwtSession";
import {refreshSessionOnce} from "@/lib/auth/refresh";
import {NextRequest, NextResponse} from "next/server";

// Pages for logged-out users. A logged-in user is sent home from them
const publicRoutes = ["/login", "/signup", "/", PENDING_GITHUB_LINK_PATH];

function redirectTo(path: string, req: NextRequest) {
    return NextResponse.redirect(new URL(path, req.nextUrl));
}

/** Where the request goes once we know whether the user is authenticated. */
function route(req: NextRequest, authenticated: boolean) {
    const isPublicRoute = publicRoutes.includes(req.nextUrl.pathname);
    if (!isPublicRoute && !authenticated) {
        return redirectTo("/login", req);
    }
    if (isPublicRoute && authenticated) {
        return redirectTo("/home", req);
    }
    // Forward the request headers, so that cookies updated after a refresh reach pages and server actions
    return NextResponse.next({request: {headers: req.headers}});
}

async function tryRefresh(refreshToken: string): Promise<TokenPair | null | "error"> {
    try {
        return await refreshSessionOnce(refreshToken);
    } catch (e) {
        console.error("Token refresh failed", e);
        return "error";
    }
}

export async function middleware(req: NextRequest) {
    const accessToken = req.cookies.get(ACCESS_COOKIE)?.value;
    const refreshToken = req.cookies.get(REFRESH_COOKIE)?.value;

    if (isAccessTokenUsable(accessToken)) {
        return route(req, true);
    }
    if (!refreshToken) {
        return route(req, false);
    }

    const tokens = await tryRefresh(refreshToken);
    if (tokens === "error") {
        // Backend unavailable: treat as logged out for this request, but keep the cookies for a retry
        return route(req, false);
    }
    if (tokens === null) {
        // Refresh token rejected (expired, reused or revoked): the session is over
        req.cookies.delete(ACCESS_COOKIE);
        req.cookies.delete(REFRESH_COOKIE);
        const res = route(req, false);
        res.cookies.delete(ACCESS_COOKIE);
        res.cookies.delete(REFRESH_COOKIE);
        return res;
    }

    const sessionCookies = getSessionCookies(tokens);
    for (const {name, value} of sessionCookies) {
        req.cookies.set(name, value);
    }
    const res = route(req, true);
    for (const {name, value, options} of sessionCookies) {
        res.cookies.set(name, value, options);
    }
    console.log("Session refreshed");
    return res;
}

// Routes on which middleware should not run
export const config = {
    matcher: ["/((?!api|_next/static|_next/image|.*\\.png$).*)"],
};
