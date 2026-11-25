import LinkGithubForm from "@/components/LinkGithubForm";
import NextImageLink from "@/components/NextImageLink";
import {getPendingGithubLink} from "@/lib/auth/githubLink";
import {redirect} from "next/navigation";

// The GitHub callback route sends a GitHub login here when its email belongs to a password account
export default async function LinkGithub() {
    const link = await getPendingGithubLink();
    if (!link) {
        redirect("/login?error=github_link_expired");
    }
    return (
        <div className="flex flex-col items-center">
            <div className="absolute start-1/5 top-2/5 flex flex-col justify-center gap-5">
                <h1 className="text-5xl font-bold text-sky-600">Virtual Crypto Exchange</h1>
                <h2 className="text-3xl">Your safe place to trade crypto</h2>
            </div>
            <div className="absolute inset-y-1/5 start-3/5">
                <LinkGithubForm email={link.email} />
            </div>
            <footer className="absolute bottom-1/10">
                <NextImageLink />
            </footer>
        </div>
    );
}
