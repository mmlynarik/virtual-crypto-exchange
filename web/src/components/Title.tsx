"use client";

import {usePathname} from "next/navigation";

const pathnameTitleMap: {[index: string]: string} = {
    explore: "Explore",
    home: "Home",
    assets: "Assets",
    transactions: "Transactions",
    invite: "Invite friends",
    rewards: "Learning rewards",
    one: "Crypto one",
    more: "More",
};

export default function Title() {
    const pathname = usePathname();
    const title = pathnameTitleMap[pathname.slice(1)]
    return <div className="text-[28px] font-bold">{title}</div>;
}
