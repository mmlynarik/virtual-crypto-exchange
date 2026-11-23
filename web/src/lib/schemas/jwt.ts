import {z} from "zod";

// Claims of an access token issued by the backend (refresh tokens carry type "refresh" plus jti and fam)
export const accessTokenSchema = z.object({
    userId: z.string().uuid(),
    type: z.literal("access"),
    aud: z.literal("vce"),
    iat: z.number(),
    exp: z.number(),
});

export type AccessTokenClaims = z.infer<typeof accessTokenSchema>;
