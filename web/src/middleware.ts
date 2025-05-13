import {isAuthenticated} from "@/lib/auth/jwtSession";
import {cookies} from "next/headers";
import {NextRequest, NextResponse} from "next/server";

const publicRoutes = ["/login", "/signup", "/"];

async function authMiddleware(req: NextRequest) {
    const path = req.nextUrl.pathname;
    const isProtectedRoute = !publicRoutes.includes(path);
    const isPublicRoute = publicRoutes.includes(path);

    const cookieStore = await cookies();
    const accessToken = cookieStore.get("access")?.value;
    const refreshToken = cookieStore.get("refresh")?.value;
    const authenticated = await isAuthenticated(req, accessToken, refreshToken);

    if (isProtectedRoute && !authenticated) {
        return NextResponse.redirect(new URL("/login", req.nextUrl));
    }
    if (isPublicRoute && authenticated) {
        return NextResponse.redirect(new URL("/home", req.nextUrl));
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
