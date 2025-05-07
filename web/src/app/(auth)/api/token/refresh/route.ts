import {refreshJWTSession} from "@/lib/actions/refresh";
import {validateJWT, verifyJWT} from "@/lib/auth/jwtSession";
import { getUserById } from "@/lib/auth/user";
import { JWTSchema } from "@/lib/schemas/jwt";
import {NextResponse, type NextRequest} from "next/server";

function get400Response(message: string) {
    return new NextResponse(message, {status: 400});
}


export async function POST(request: NextRequest) {
    const body = await request.json();
    const token = body.refreshToken;

    if (!token) {
        return get400Response("Refresh token is missing");
    }
    const verifiedPayload = await verifyJWT(token);
    if (!verifiedPayload) {
        return get400Response("Refresh token verification failed");
    }
    const validatedPayload = await validateJWT(verifiedPayload);
    if (!validatedPayload.success) {
        return get400Response("Refresh token validation failed");
    }
    const payload: JWTSchema = validatedPayload.data;
    const user = await getUserById(payload.userId);
    if (!user) {
        return get400Response("User in refresh token does not exist");
    }

    const {accessToken, refreshToken} = await refreshJWTSession(payload);
    return NextResponse.json({accessToken, refreshToken});
}
