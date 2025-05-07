"use server";

import {JWT_REFRESH_IF_LESS_THAN} from "@/config";
import {createJWTSession} from "../auth/jwtSession";
import {JWTSchema} from "../schemas/jwt";

function getSecondsUntilExpiration(payload: JWTSchema) {
    const expiration = new Date(payload.exp * 1000);
    const now = new Date();
    return (expiration.getTime() - now.getTime()) / 1000;
}

export async function refreshJWTSession(payload: JWTSchema) {
    const {accessToken, refreshToken} = await createJWTSession(payload.userId);
    const secondsUntilExpiration = getSecondsUntilExpiration(payload);
    if (secondsUntilExpiration < JWT_REFRESH_IF_LESS_THAN) {
        return {accessToken, refreshToken};
    } else {
        return {accessToken, refreshToken: null};
    }
}
