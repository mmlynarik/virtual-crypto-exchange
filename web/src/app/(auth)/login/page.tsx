import LoginForm from "@/components/LoginForm";
import NextImageLink from "@/components/NextImageLink";

export default function Login() {
    return (
        <div className="flex flex-col gap-30 items-center">
            <div className="mt-45 flex items-center justify-center gap-50">
                <div className="flex flex-col gap-5">
                    <h1 className="text-5xl font-bold text-sky-600">Virtual Crypto Exchange</h1>
                    <h2 className="text-3xl">Your safe place to trade crypto</h2>
                </div>
                <LoginForm />
            </div>
            <footer className="fixed bottom-1/10">
                <NextImageLink />
            </footer>
        </div>
    );
}
