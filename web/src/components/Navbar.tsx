"use client";
// import LogoutButton from "@/components/LogoutButton";
import { ChartPie, House, LucideProps, ReceiptText } from "lucide-react";
import Image from "next/image";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { ComponentType } from "react";

{
    /* grip ellipsis-vertical bell */
}

type NavItemProps = {
    Icon: ComponentType<LucideProps>;
    name: string;
    href: string;
    hasMargin?: boolean;
};

function NavItem({Icon, name, href, hasMargin}: NavItemProps) {
    const pathname = usePathname();
    const isActive = (href: string) => href === pathname;
    return (
        <Link
            href={href}
            className={`flex gap-4 ${isActive(href) ? "bg-sky-50" : ""} ${hasMargin ? "mt-auto" : ""} rounded-full p-4 hover:bg-slate-100 active:bg-slate-200`}
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
        <nav className="w-60 border-r-1 p-3.25 h-screen">
            <div className="flex flex-col h-full">
                <div className="mr-auto pt-3 pb-9 pl-3">
                    <Link href="/home">
                        <CoinbaseLogo />
                    </Link>
                </div>
                <div className="flex h-full flex-col gap-1">
                    <NavItem Icon={House} name="Home" href="/home" />
                    <NavItem Icon={ChartPie} name="My assets" href="/assets" />
                    <NavItem Icon={ReceiptText} name="Transactions" href="/transactions" />
                    <NavItem Icon={ReceiptText} name="Sign out" href="/transactions" hasMargin={true} />
                </div>
            </div>
        </nav>
    );
}
