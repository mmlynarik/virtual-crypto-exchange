"use client";

import {Button} from "@/components/ui/button";
import {Card, CardContent, CardHeader, CardTitle} from "@/components/ui/card";
import {Input} from "@/components/ui/input";
import {Label} from "@/components/ui/label";
import {cancelGithubLink, linkGithubAction} from "@/lib/actions/githubLink";
import {GithubLinkSchema, githubLinkSchema} from "@/lib/schemas/githubLink";
import {zodResolver} from "@hookform/resolvers/zod";
import {useActionState, useEffect, useState, useTransition} from "react";
import {useForm} from "react-hook-form";
import ErrorField from "./ErrorField";
import FormButton from "./FormButton";
import {Form, FormControl, FormField, FormItem, FormLabel} from "./ui/form";

/**
 * Asks for the password of the account that a GitHub login found by email. Only the email is passed in:
 * the pending link token stays in its httpOnly cookie, which the server action reads.
 */
export default function LinkGithubForm({email}: {email: string}) {
    const [formState, formAction, isPending] = useActionState(linkGithubAction, {success: false});
    const [isCancelling, startCancel] = useTransition();
    const [isErrorShown, setIsErrorShown] = useState<boolean>(true);
    const form = useForm<GithubLinkSchema>({
        resolver: zodResolver(githubLinkSchema),
        defaultValues: {password: ""},
    });
    const passwordError = formState?.errors?.password?.[0];

    useEffect(() => {
        setIsErrorShown(true);
    }, [formState]);

    return (
        <Card className="flex w-xs flex-col gap-9">
            <CardHeader>
                <CardTitle className="text-center text-3xl">Connect GitHub</CardTitle>
            </CardHeader>
            <CardContent>
                <Form {...form}>
                    <form className="flex flex-col gap-6" action={formAction}>
                        <p className="text-center text-sm">
                            An account with <strong>{email}</strong> already exists. Enter its password to
                            connect your GitHub account. You can then log in with either.
                        </p>
                        {formState?.errors?.root && isErrorShown && (
                            <ErrorField
                                message={formState.errors.root[0]}
                                onClose={() => setIsErrorShown(false)}
                            />
                        )}
                        <div className="grid gap-3">
                            <Label htmlFor="link-github-email">Email</Label>
                            {/* Read-only, but submitted, so password managers offer this account's password */}
                            <Input
                                id="link-github-email"
                                name="email"
                                value={email}
                                readOnly
                                autoComplete="username"
                                className="bg-gray-100"
                            />
                        </div>
                        <FormField
                            control={form.control}
                            name="password"
                            render={({field}) => (
                                <FormItem className="grid gap-3">
                                    <FormLabel>Password</FormLabel>
                                    <FormControl>
                                        <Input
                                            placeholder="Enter your password"
                                            type="password"
                                            autoComplete="current-password"
                                            autoFocus
                                            {...field}
                                        />
                                    </FormControl>
                                    {passwordError && <p className="text-sm text-red-600">{passwordError}</p>}
                                </FormItem>
                            )}
                        />
                        <div className="grid gap-3">
                            <FormButton
                                label="Connect GitHub and log in"
                                labelPending="Connecting"
                                isPending={isPending}
                            />
                            <Button
                                type="button"
                                variant="outline"
                                disabled={isPending || isCancelling}
                                onClick={() => startCancel(cancelGithubLink)}
                            >
                                Cancel
                            </Button>
                        </div>
                    </form>
                </Form>
            </CardContent>
        </Card>
    );
}
