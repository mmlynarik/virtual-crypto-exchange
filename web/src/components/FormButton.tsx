import {Button} from "@/components/ui/button";
import LoadingButtonLabel from "./LoadingButtonLabel";

type FormButterProps = {
    label: string;
    labelPending: string;
    isPending: boolean;
};

export default function FormButton({label, labelPending, isPending}: FormButterProps) {
    return (
        <Button type="submit" disabled={isPending} className="bg-sky-600 transition hover:bg-sky-700">
            {isPending ? <LoadingButtonLabel label={labelPending} /> : label}
        </Button>
    );
}
