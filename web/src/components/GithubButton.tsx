import {GitHubIcon} from "@/components/GithubIcon";
import {Button} from "./ui/button";
import {githubLogin} from "@/lib/actions/login";
import {useTransition} from "react";
import {LoaderCircle} from "lucide-react";

export default function GithubButton() {
    const [isPending, startTransition] = useTransition();
    return (
        <Button
            type="button"
            disabled={isPending}
            className="w-full bg-gray-600 transition hover:bg-gray-700"
            onClick={() => startTransition(githubLogin)}
        >
            <div className="flex items-center gap-3">
                {isPending && <LoaderCircle className="animate-spin" />}
                <span className="fill-current">
                    <GitHubIcon />
                </span>
                <span>Log{isPending && "ging"} in with Github</span>
            </div>
        </Button>
    );
}
