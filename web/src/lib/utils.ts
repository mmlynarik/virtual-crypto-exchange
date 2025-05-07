import {clsx, type ClassValue} from "clsx";
import {twMerge} from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
    return twMerge(clsx(inputs));
}

export function getFieldsFromFormData(formData: FormData) {
    const formDataObject = Object.fromEntries(formData);
    const fields: Record<string, string> = {};
    for (const key of Object.keys(formDataObject)) {
        fields[key] = formDataObject[key].toString();
    }
    return fields;
}
