// import LogoutButton from "@/components/LogoutButton";

import NavBar from "@/components/Navbar";


export default function DashboardLayout({
    children,
}: Readonly<{
    children: React.ReactNode;
}>) {
    return (
        <div className="flex bg-white">
            <NavBar />
            {children}
        </div>
    );
}
