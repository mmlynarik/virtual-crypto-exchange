import LoginForm from "@/components/LoginForm";
import NextImageLink from "@/components/NextImageLink";

export default function Login() {
    return (
        <div className="flex flex-col items-center font-sans">
            <div className="absolute start-1/5 top-2/5 flex flex-col justify-center gap-5">
                <h1 className="text-5xl font-bold text-sky-600">Virtual Crypto Exchange</h1>
                <h2 className="text-3xl">Your safe place to trade crypto</h2>
            </div>
            <div className="absolute inset-y-1/5 start-3/5">
                <LoginForm />
            </div>
            <footer className="absolute bottom-1/10">
                <NextImageLink />
            </footer>
        </div>
    );
}
