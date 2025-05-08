import NextImageLink from "@/components/NextImageLink";
import SignUpForm from "@/components/SignUpForm";

export default function SignUp() {
    return (
        <div className="flex flex-col items-center gap-30">
            <div className="mt-40 flex items-center justify-center gap-50">
                <div className="flex flex-col gap-5">
                    <h1 className="text-5xl font-bold text-sky-600">Virtual Crypto Exchange</h1>
                    <h2 className="text-3xl">Your safe place to trade crypto</h2>
                </div>
                <SignUpForm />
            </div>
            <footer>
                <NextImageLink />
            </footer>
        </div>
    );
}
