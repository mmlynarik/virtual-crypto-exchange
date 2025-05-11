"use client";
// import LogoutButton from "@/components/LogoutButton";
import Image from "next/image";
import {House, ChartPie, ReceiptText, LucideProps} from "lucide-react";
import {ComponentType} from "react";
import Link from "next/link";
import {usePathname} from "next/navigation";

{
    /* grip ellipsis-vertical bell */
}

type NavItemProps = {
    Icon: ComponentType<LucideProps>;
    name: string;
    href: string;
};

function NavItem({Icon, name, href}: NavItemProps) {
    const pathname = usePathname();
    const isActive = (href: string) => href === pathname;
    return (
        <Link
            href={href}
            className={`${isActive(href) ? "bg-sky-50" : ""} flex items-center gap-4 rounded-full p-4 hover:bg-slate-100 active:bg-slate-200`}
        >
            {<Icon color={`${isActive(href) ? "#0084d1" : "black"}`} />}
            <span className={`${isActive(href) ? "text-sky-600" : ""} font-bold`}>{name}</span>
        </Link>
    );
}

function CoinbaseLogo() {
    return <Image className="size-8" src="/coinbase-logo.png" width={25} height={25} alt="Coinbase logo" />;
}

export default function NavBar() {
    return (
        <nav className="min-h-screen w-60 border-r-1 p-3.25">
            <div className="flex flex-col">
                <div className="flex pt-3 pb-9 pl-3">
                    <Link href="/home">
                        <CoinbaseLogo />
                    </Link>
                </div>
                <div className="flex flex-col gap-1">
                    <NavItem Icon={House} name="Home" href="/home" />
                    <NavItem Icon={ChartPie} name="My assets" href="/assets" />
                    <NavItem Icon={ReceiptText} name="Transactions" href="/transactions" />
                </div>
            </div>
        </nav>
    );
}
