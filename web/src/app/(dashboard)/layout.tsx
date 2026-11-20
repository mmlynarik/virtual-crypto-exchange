import Header from "@/components/Header";
import NavBar from "@/components/Navbar";
import {getCurrentUser, getDisplayName} from "@/lib/user";

export default async function DashboardLayout({
    children,
}: Readonly<{
    children: React.ReactNode;
}>) {
    const user = await getCurrentUser();
    return (
        <div className="flex bg-white">
            <NavBar />
            <div className="flex w-full flex-col">
                <Header userName={getDisplayName(user)} />
                {children}
            </div>
        </div>
    );
}
