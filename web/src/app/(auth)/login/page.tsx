import LoginForm from "@/components/LoginForm";
import NextImageLink from "@/components/NextImageLink";

export default function Login() {
    return (
        <div className="grid max-h-screen grid-rows-[20px_1fr_20px] items-center justify-items-center gap-15 font-[family-name:var(--font-geist-sans)] sm:p-15">
            <main className="row-start-2 flex flex-col items-center gap-12">
                <h1 className="text-3xl">Welcome to Virtual Crypto Exchange</h1>
                <LoginForm />
            </main>
            <footer className="row-start-3 flex justify-center">
                <NextImageLink />
            </footer>
        </div>
    );
}
