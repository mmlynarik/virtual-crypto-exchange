"use client";

import {Card, CardContent, CardFooter, CardHeader, CardTitle} from "@/components/ui/card";
import {Form, FormControl, FormField, FormItem, FormLabel, FormMessage} from "@/components/ui/form";
import {Input} from "@/components/ui/input";
import {signUpAction} from "@/lib/actions/signup";
import {signUpSchema, SignUpSchema} from "@/lib/schemas/signup";
import {zodResolver} from "@hookform/resolvers/zod";
import Link from "next/link";
import {startTransition, useActionState, useRef} from "react";
import {useForm} from "react-hook-form";
import FormButton from "./FormButton";

export default function SignUpForm() {
    const [formState, formAction, isPending] = useActionState(signUpAction, {success: false});
    const formRef = useRef<HTMLFormElement>(null);
    const lastSubmittedValues = formState?.fields ?? {};
    const form = useForm<SignUpSchema>({
        resolver: zodResolver(signUpSchema),
        defaultValues: {
            email: "",
            password: "",
            confirmPassword: "",
            ...lastSubmittedValues,
        },
        mode: "onBlur",
    });

    return (
        <Card className="flex w-xs flex-col gap-9">
            <CardHeader>
                <CardTitle className="text-center text-3xl">Sign Up</CardTitle>
            </CardHeader>
            <CardContent>
                <Form {...form}>
                    <form
                        ref={formRef}
                        className="flex flex-col gap-6"
                        onSubmit={(e) => {
                            form.handleSubmit(() => {
                                startTransition(() => formAction(new FormData(formRef.current!)));
                            })(e);
                        }}
                        action={formAction}
                    >
                        <FormField
                            control={form.control}
                            name="email"
                            render={({field}) => (
                                <FormItem className="grid gap-3">
                                    <FormLabel>Email</FormLabel>
                                    <FormControl>
                                        <Input placeholder="Enter your email" autoFocus {...field} />
                                    </FormControl>
                                    <FormMessage>
                                        {formState?.errors?.email && formState.errors.email[0]}
                                    </FormMessage>
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
                                    <FormMessage>
                                        {formState?.errors?.password && formState.errors.password[0]}
                                    </FormMessage>
                                </FormItem>
                            )}
                        />

                        <FormField
                            control={form.control}
                            name="confirmPassword"
                            render={({field}) => (
                                <FormItem className="grid gap-3">
                                    <FormLabel>Confirm password</FormLabel>
                                    <FormControl>
                                        <Input
                                            placeholder="Repeat your password"
                                            type="password"
                                            {...field}
                                        />
                                    </FormControl>
                                    <FormMessage>
                                        {formState?.errors?.confirmPassword &&
                                            formState.errors.confirmPassword[0]}
                                    </FormMessage>
                                </FormItem>
                            )}
                        />
                        <FormButton label="Sign up" labelPending="Signing up" isPending={isPending} />
                    </form>
                </Form>
            </CardContent>
            <CardFooter className="flex justify-center gap-2 text-sm">
                Already have an account?
                <Link href="/login" className="underline underline-offset-4">
                    Login
                </Link>
            </CardFooter>
        </Card>
    );
}
