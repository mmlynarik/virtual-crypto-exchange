"use server";

import {GITHUB_AUTHORIZE_URL} from "@/config";
import {loginWithPassword} from "@/lib/auth/backend";
import {setSessionCookies} from "@/lib/auth/jwtSession";
import {redirect} from "next/navigation";
import {loginSchema} from "../schemas/login";
import {getFieldsFromFormData} from "../utils";

type FormState = {
    success: boolean;
    fields?: Record<string, string>;
    errors?: Record<string, string[]>;
};

export async function loginAction(_: FormState, formData: FormData): Promise<FormState> {
    const formDataObject = Object.fromEntries(formData);
    const parsed = loginSchema.safeParse(formDataObject);

    if (!parsed.success) {
        const errors = parsed.error.flatten().fieldErrors;
        const fields = getFieldsFromFormData(formData);
        return {success: false, fields, errors};
    }

    const tokens = await loginWithPassword(parsed.data.email, parsed.data.password);
    if (!tokens) {
        return {success: false, errors: {root: ["Incorrect email or password"]}};
    }

    await setSessionCookies(tokens);
    redirect("/home");
}

export async function githubLogin() {
    redirect(GITHUB_AUTHORIZE_URL);
}
