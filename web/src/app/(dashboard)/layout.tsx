import NavBar from "@/components/Navbar";
import Title from "@/components/Title";

function Header() {
    return (
        <header className="flex h-[75px] flex-col border-b-1 px-8 pt-4">
            <div className="flex justify-between">
                <div className="flex grow justify-start">
                    <Title />
                </div>
                <div className="flex">
                    <div className="text-[28px] font-bold">Search</div>
                </div>
            </div>
        </header>
    );
}

export default function DashboardLayout({
    children,
}: Readonly<{
    children: React.ReactNode;
}>) {
    return (
        <div className="flex bg-white">
            <NavBar />
            <div className="flex w-full flex-col">
                <Header />
                {children}
            </div>
        </div>
    );
}
