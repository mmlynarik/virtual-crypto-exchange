import NextImageLink from "@/components/NextImageLink";
import SignUpForm from "@/components/SignUpForm";

export default function SignUp() {
    return (
        <div className="flex flex-col items-center">
            <div className="absolute start-1/5 top-2/5 flex flex-col justify-center gap-5">
                <h1 className="text-5xl font-bold text-sky-600">Virtual Crypto Exchange</h1>
                <h2 className="text-3xl">Your safe place to trade crypto</h2>
            </div>
            <div className="absolute inset-y-2/11 start-3/5">
                <SignUpForm />
            </div>
            <footer className="absolute bottom-1/10">
                <NextImageLink />
            </footer>
        </div>
    );
}
