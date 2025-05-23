import Header from "@/components/Header";
import NavBar from "@/components/Navbar";

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
