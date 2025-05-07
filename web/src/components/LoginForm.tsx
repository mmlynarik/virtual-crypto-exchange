"use client";

import {Card, CardContent, CardFooter, CardHeader, CardTitle} from "@/components/ui/card";
import {Input} from "@/components/ui/input";
import {X} from "lucide-react";
import {loginAction} from "@/lib/actions/login";
import {LoginSchema, loginSchema} from "@/lib/schemas/login";
import {zodResolver} from "@hookform/resolvers/zod";
import Link from "next/link";
import {Dispatch, SetStateAction, useActionState, useEffect, useState} from "react";
import {useForm} from "react-hook-form";
import FormButton from "./FormButton";
import GithubButton from "./GithubButton";
import SignInOrLine from "./SignInOrLine";
import {Form, FormControl, FormField, FormItem, FormLabel} from "./ui/form";

type CredentialsErrorFieldProps = {
    setIsCredentialsError: Dispatch<SetStateAction<boolean>>;
};

function CredentialsErrorField(props: CredentialsErrorFieldProps) {
    return (
        <>
            <div className="flex items-center justify-center gap-4 rounded-xs bg-red-100 py-2 text-center text-sm outline-1 outline-red-200">
                <span>Incorrect username or password.</span>
                <X
                    onClick={() => props.setIsCredentialsError(false)}
                    className="size-[16px] cursor-pointer bg-red-100 p-0 text-red-500"
                />
            </div>
        </>
    );
}

export default function LoginForm() {
    const [formState, formAction, isPending] = useActionState(loginAction, {success: false});
    const lastSubmittedValues = formState?.fields ?? {};
    const [isCredentialsError, setIsCredentialsError] = useState<boolean>(true);
    const form = useForm<LoginSchema>({
        resolver: zodResolver(loginSchema),
        defaultValues: {
            email: "",
            password: "",
            ...lastSubmittedValues,
        },
    });

    useEffect(() => {
        setIsCredentialsError(true);
    }, [formState]);

    return (
        <Card className="flex w-xs flex-col gap-9">
            <CardHeader>
                <CardTitle className="text-center text-3xl">Login</CardTitle>
            </CardHeader>
            <CardContent>
                <Form {...form}>
                    <form className="flex flex-col gap-6" action={formAction}>
                        {formState?.errors?.root && isCredentialsError && (
                            <CredentialsErrorField setIsCredentialsError={setIsCredentialsError} />
                        )}
                        <FormField
                            control={form.control}
                            name="email"
                            render={({field}) => (
                                <FormItem className="grid gap-3">
                                    <FormLabel>Email</FormLabel>
                                    <FormControl>
                                        <Input placeholder="Enter your email" autoFocus {...field} />
                                    </FormControl>
                                </FormItem>
                            )}
                        />
                        <FormField
                            control={form.control}
                            name="password"
                            render={({field}) => (
                                <FormItem className="grid gap-3">
                                    <FormLabel>Password</FormLabel>
                                    <FormControl>
                                        <Input placeholder="Enter your password" type="password" {...field} />
                                    </FormControl>
                                </FormItem>
                            )}
                        />
                        <div className="grid gap-3">
                            <FormButton label="Log in" labelPending="Logging in" isPending={isPending} />
                            <SignInOrLine />
                            <GithubButton />
                        </div>
                    </form>
                </Form>
            </CardContent>
            <CardFooter className="flex justify-center gap-1 text-sm">
                Don&apos;t have an account?
                <Link href="/signup" className="underline underline-offset-4">
                    Sign up
                </Link>
            </CardFooter>
        </Card>
    );
}
