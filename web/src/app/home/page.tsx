// import LogoutButton from "@/components/LogoutButton";
import Image from "next/image";
import {House, ChartPie, ReceiptText } from "lucide-react";
import {ReactElement} from "react";

{
    /*  house chart-pie receipt-text grip ellipsis-vertical bell */
}

type NavItemProps = {
    icon: ReactElement;
    name: string;
};

function NavItem({icon, name}: NavItemProps) {
    return (
        <div className="p-4">
            <div className="flex items-center gap-4">
                {icon}
                <span className="font-bold">{name}</span>
            </div>
        </div>
    );
}

export default function Home() {
    return (
        <div className="flex bg-white">
            <nav className="min-h-screen w-[240px] border-r-1 p-3.25">
                <div className="flex flex-col">
                    <div className="pt-3 pl-3 pb-8">
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
            <main>
                <h1>Home</h1>
            </main>
        </div>
    );
}
