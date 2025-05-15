"use client";
// import LogoutButton from "@/components/LogoutButton";
import {
    ChartPie,
    House,
    LucideProps,
    ReceiptText,
    LogOut,
    Compass,
    UserPlus,
    Coins,
    Award,
    EllipsisVertical,
} from "lucide-react";
import Image from "next/image";
import Link from "next/link";
import {usePathname} from "next/navigation";
import {ComponentType} from "react";
import {logout} from "@/lib/actions/logout";
import {Button} from "./ui/button";

/* grip bell */

type NavLinkProps = {
    Icon: ComponentType<LucideProps>;
    name: string;
    href: string;
};

type NavLogoutButtonProps = {
    Icon: ComponentType<LucideProps>;
    name: string;
};

function NavLogoutButton({Icon, name}: NavLogoutButtonProps) {
    return (
        <Button
            variant="outline"
            onClick={async () => await logout()}
            className="mt-auto mb-2 ml-1 flex cursor-pointer justify-start gap-3 rounded-full py-6 hover:bg-rose-100 active:bg-red-200"
        >
            <div className="px-1">{<Icon color="red" />}</div>
            <span className="font-bold text-rose-600">{name}</span>
        </Button>
    );
}

function NavLink({Icon, name, href}: NavLinkProps) {
    const pathname = usePathname();
    const isActive = (href: string) => href === pathname;
    return (
        <Link
            href={href!}
            className={`flex gap-4 ${isActive(href!) ? "bg-sky-50" : ""} rounded-full p-4 hover:bg-slate-100 active:bg-slate-200`}
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
                <div className="flex h-full flex-col gap-1.25">
                    <NavLink Icon={House} name="Home" href="/home" />
                    <NavLink Icon={ChartPie} name="My assets" href="/assets" />
                    <NavLink Icon={ReceiptText} name="Transactions" href="/transactions" />
                    <NavLink Icon={Compass} name="Explore" href="/explore" />
                    <NavLink Icon={Coins} name="Crypto One" href="/one" />
                    <NavLink Icon={UserPlus} name="Invite friends" href="/invite" />
                    <NavLink Icon={Award} name="Learning rewards" href="/rewards" />
                    <NavLink Icon={EllipsisVertical} name="More" href="/more" />
                    <NavLogoutButton Icon={LogOut} name="Sign out" />
                </div>
            </div>
        </nav>
    );
}
