import {z} from "zod";

export const jwtSchema = z.object({
    userId: z.number(),
    aud: z.literal("vce"),
    iat: z.number(),
    exp: z.number(),
});

export type JWTPrivateClaims = {
    userId: number;
};

export type JWTSchema = z.infer<typeof jwtSchema>;
