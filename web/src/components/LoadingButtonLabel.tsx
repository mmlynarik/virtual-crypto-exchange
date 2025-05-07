import { LoaderCircle } from "lucide-react";

export default function LoadingButtonLabel({label}: {label: string}) {
    return (
        <div className="flex items-center gap-3">
            <LoaderCircle className="animate-spin" /> {label}
        </div>
    );
}
