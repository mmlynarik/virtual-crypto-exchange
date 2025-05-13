"use client";
// import LogoutButton from "@/components/LogoutButton";
import {ChartPie, House, LucideProps, ReceiptText, LogOut} from "lucide-react";
import Image from "next/image";
import Link from "next/link";
import {usePathname} from "next/navigation";
import {ComponentType} from "react";
import {logout} from "@/lib/actions/logout";
import {Button} from "./ui/button";

{
    /* grip ellipsis-vertical bell */
}

function NavItemButton({Icon, name}: NavItemProps) {
    return (
        <Button
            onClick={async () => await logout()}
            className="mt-auto mb-2 ml-1 flex cursor-pointer justify-start gap-3 rounded-full bg-red-50 py-7 hover:bg-red-100 active:bg-red-200"
        >
            <div className="px-1">{<Icon color="red" />}</div>
            <span className="font-bold text-red-500">{name}</span>
        </Button>
    );
}

type NavItemProps = {
    Icon: ComponentType<LucideProps>;
    name: string;
    href?: string;
    hasMargin?: boolean;
};

function NavItem({Icon, name, href, hasMargin}: NavItemProps) {
    const pathname = usePathname();
    const isActive = (href: string) => href === pathname;
    return (
        <Link
            href={href!}
            className={`flex gap-4 ${isActive(href!) ? "bg-sky-50" : ""} ${hasMargin ? "mt-auto" : ""} rounded-full p-4 hover:bg-slate-100 active:bg-slate-200`}
        >
            {<Icon color={`${isActive(href!) ? "#0084d1" : "black"}`} />}
            <span className={`${isActive(href!) ? "text-sky-600" : ""} font-bold`}>{name}</span>
        </Link>
    );
}

function CoinbaseLogo() {
    return <Image className="size-8" src="/coinbase-logo.png" width={25} height={25} alt="Coinbase logo" />;
}

export default function NavBar() {
    return (
        <nav className="h-screen w-60 border-r-1 p-3.25">
            <div className="flex h-full flex-col">
                <div className="mr-auto pt-3 pb-9 pl-3">
                    <Link href="/home">
                        <CoinbaseLogo />
                    </Link>
                </div>
                <div className="flex h-full flex-col gap-1">
                    <NavItem Icon={House} name="Home" href="/home" />
                    <NavItem Icon={ChartPie} name="My assets" href="/assets" />
                    <NavItem Icon={ReceiptText} name="Transactions" href="/transactions" />
                    <NavItemButton Icon={LogOut} name="Sign out" />
                </div>
            </div>
        </nav>
    );
}
