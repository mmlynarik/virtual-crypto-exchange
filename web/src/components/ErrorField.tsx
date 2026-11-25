import {X} from "lucide-react";

type ErrorFieldProps = {
    message: string;
    onClose: () => void;
};

/** A dismissible error box at the top of a form. */
export default function ErrorField(props: ErrorFieldProps) {
    return (
        <div className="flex items-center gap-3 rounded-sm bg-red-100 px-4 py-3 text-sm outline-1 outline-red-200">
            <span className="flex-1 text-center">{props.message}</span>
            <button
                type="button"
                aria-label="Dismiss"
                onClick={props.onClose}
                className="shrink-0 cursor-pointer text-red-500 hover:text-red-700"
            >
                <X className="size-5" />
            </button>
        </div>
    );
}
