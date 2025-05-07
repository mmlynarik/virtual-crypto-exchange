"use server";

import {redirect} from "next/navigation";
import {deleteJWTSession} from "../auth/jwtSession";

export async function logout() {
    await deleteJWTSession();
    redirect("/login");
}
