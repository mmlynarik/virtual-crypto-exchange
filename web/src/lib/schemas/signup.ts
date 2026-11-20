import {checkEmailAvailable} from "@/lib/actions/signup";
import {z} from "zod";

let lastValue: string | null = null;
let lastResult: boolean | null = null;

export async function checkEmailAvailableOnActive(value: string) {
    if (value === lastValue && lastResult !== null) {
        return lastResult;
    }
    const result = await checkEmailAvailable(value);
    lastValue = value;
    lastResult = result;
    return result;
}

export const signUpSchema = z
    .object({
        email: z
            .string()
            .trim()
            .email("Invalid email format")
            .refine(checkEmailAvailableOnActive, "Email is already in use"),
        // Same limits as the backend's EmailCredentials.
        password: z
            .string()
            .min(8, "Password must have at least 8 characters")
            .max(128, "Password must have at most 128 characters"),
        confirmPassword: z.string(),
    })
    .refine((data) => data.password === data.confirmPassword, {
        message: "Passwords must match",
        path: ["confirmPassword"],
    });

export type SignUpSchema = z.infer<typeof signUpSchema>;
