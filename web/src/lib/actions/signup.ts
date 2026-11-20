"use server";

import {isEmailAvailable, registerWithPassword} from "@/lib/auth/backend";
import {setSessionCookies} from "@/lib/auth/jwtSession";
import {signUpSchema} from "@/lib/schemas/signup";
import {getFieldsFromFormData} from "@/lib/utils";
import {redirect} from "next/navigation";

type FormState = {
    success: boolean;
    fields?: Record<string, string>;
    errors?: Record<string, string[]>;
};

export async function signUpAction(formState: FormState, formData: FormData): Promise<FormState> {
    const formDataAsObject = Object.fromEntries(formData);
    const parsed = await signUpSchema.safeParseAsync(formDataAsObject);
    const fields = getFieldsFromFormData(formData);

    if (!parsed.success) {
        const errors = parsed.error.flatten().fieldErrors;
        return {success: false, fields, errors};
    }

    // The backend creates the user and starts a session in one call
    const result = await registerWithPassword(parsed.data.email, parsed.data.password);
    if (!result.ok) {
        const errors = result.reason === "email_taken" ? {email: ["Email is already in use"]} : result.errors;
        return {success: false, fields, errors};
    }

    await setSessionCookies(result.tokens);
    redirect("/home");
}

export async function checkEmailAvailable(email: string) {
    return isEmailAvailable(email);
}
