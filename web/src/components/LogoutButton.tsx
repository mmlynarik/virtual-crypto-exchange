"use client";

import {logout} from "@/lib/actions/logout";
import {Button} from "./ui/button";

export default function LogoutButton() {
    return (
        <Button
            variant="destructive"
            onClick={async () => await logout()}
            className="cursor-pointer rounded-2xl px-4 py-4"
        >
            Logout
        </Button>
    );
}
