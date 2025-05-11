// import LogoutButton from "@/components/LogoutButton";
import Image from "next/image";
import {House, ChartPie, ReceiptText} from "lucide-react";
import {ReactElement} from "react";
import Link from "next/link";

{
    /* grip ellipsis-vertical bell */
}

type NavItemProps = {
    icon: ReactElement;
    name: string;
};

function NavItem({icon, name}: NavItemProps) {
    return (
        <div className="rounded-full p-4 hover:bg-slate-100 active:bg-sky-50">
            <Link href="/assets" className="flex items-center gap-4">
                {icon}
                <span className="font-bold">{name}</span>
            </Link>
        </div>
    );
}

function NavBar() {
    return (
        <nav className="min-h-screen w-60 border-r-1 p-3.25">
            <div className="flex flex-col">
                <div className="pt-3 pb-9 pl-3">
                    <Image
                        className="size-8"
                        src="/coinbase-logo.png"
                        width={25}
                        height={25}
                        alt="Coinbase logo"
                    />
                </div>
                <div className="flex flex-col gap-1">
                    <NavItem icon={<House />} name="Home" />
                    <NavItem icon={<ChartPie />} name="My assets" />
                    <NavItem icon={<ReceiptText />} name="Transactions" />
                </div>
            </div>
        </nav>
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
            {children}
        </div>
    );
}
