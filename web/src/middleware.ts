import {IsTokenOK, setJWTSessionHeader} from "@/lib/auth/jwtSession";
import {cookies} from "next/headers";
import {NextRequest, NextResponse} from "next/server";

const protectedRoutes = ["/dashboard"];
const publicRoutes = ["/login", "/signup", "/"];

async function authMiddleware(req: NextRequest) {
    const path = req.nextUrl.pathname;
    const isProtectedRoute = protectedRoutes.includes(path);
    const isPublicRoute = publicRoutes.includes(path);

    const cookieStore = await cookies();
    const access_token = cookieStore.get("access")?.value;
    const authenticated = await IsTokenOK(access_token);

    if (isProtectedRoute && !authenticated) {
        const token = cookieStore.get("refresh")?.value;
        const res = await fetch(`${req.nextUrl.origin}/api/token/refresh`, {
            method: "POST",
            body: JSON.stringify({refreshToken: token}),
            headers: {Accept: "application/json"},
        });
        if (!res.ok) {
            return NextResponse.redirect(new URL("/login", req.nextUrl));
        }
        const {accessToken, refreshToken} = await res.json();
        setJWTSessionHeader(accessToken, refreshToken);
        console.log(`Access token ${refreshToken ? "and refresh token " : ""}refreshed`);
        return NextResponse.next();
    }
    if (isPublicRoute && authenticated) {
        return NextResponse.redirect(new URL("/dashboard", req.nextUrl));
    }
    return NextResponse.next();
}

export default async function middleware(req: NextRequest) {
    const res = authMiddleware(req);
    return res;
}

// Routes on which middleware should not run
export const config = {
    matcher: ["/((?!api|_next/static|_next/image|.*\\.png$).*)"],
};
