import {z} from "zod";

export const githubLinkSchema = z.object({
    password: z.string().min(1, "Enter your password"),
});

export type GithubLinkSchema = z.infer<typeof githubLinkSchema>;
