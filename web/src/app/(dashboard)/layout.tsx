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
    link: string;
};

function NavItem({icon, name, link}: NavItemProps) {
    return (
        <Link
            href={link}
            className="flex items-center gap-4 rounded-full p-4 hover:bg-slate-100 active:bg-sky-50"
        >
            {icon}
            <span className="font-bold">{name}</span>
        </Link>
    );
}

function NavBar() {
    return (
        <nav className="min-h-screen w-60 border-r-1 p-3.25">
            <div className="flex flex-col">
                <div className="flex pt-3 pb-9 pl-3">
                    <Link href="/home">
                        <Image
                            className="size-8"
                            src="/coinbase-logo.png"
                            width={25}
                            height={25}
                            alt="Coinbase logo"
                        />
                    </Link>
                </div>
                <div className="flex flex-col gap-1">
                    <NavItem icon={<House />} name="Home" link="/home" />
                    <NavItem icon={<ChartPie />} name="My assets" link="/assets" />
                    <NavItem icon={<ReceiptText />} name="Transactions" link="/transactions" />
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
