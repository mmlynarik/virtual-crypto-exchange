// next/navigation's redirect() ends a request by throwing. Tests mock it with this module:
//
//     vi.mock("next/navigation", () => import("../test/nextNavigation"));
//
// and read where the code under test redirected to with redirectedTo().

export class Redirect extends Error {
    constructor(public url: string) {
        super(`redirect to ${url}`);
    }
}

export function redirect(url: string): never {
    throw new Redirect(url);
}

/** Runs fn and returns the URL it redirected to; throws if it returned or failed without redirecting. */
export async function redirectedTo(fn: () => Promise<unknown>): Promise<string> {
    try {
        await fn();
    } catch (e) {
        if (e instanceof Redirect) {
            return e.url;
        }
        throw e;
    }
    throw new Error("Expected a redirect");
}
