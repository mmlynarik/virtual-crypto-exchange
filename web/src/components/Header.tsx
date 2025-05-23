"use client";

import Title from "@/components/Title";
import {Button} from "@/components/ui/button";
import {FaRegBell} from "react-icons/fa";
import {RiQuestionMark} from "react-icons/ri";
import {BsFillGrid3X3GapFill} from "react-icons/bs";

export default function Header() {
    return (
        <header className="flex h-[75px] flex-col border-b-1 px-8 pt-4">
            <div className="flex justify-between">
                <div className="flex grow justify-start">
                    <Title />
                </div>
                <div className="flex gap-x-2.25 pt-0.25 pr-3.5">
                    <Button className="size-[40px] cursor-pointer rounded-full bg-gray-200 hover:bg-gray-300">
                        <FaRegBell color="black" />
                    </Button>
                    <Button className="size-[40px] cursor-pointer rounded-full bg-gray-200 hover:bg-gray-300">
                        <RiQuestionMark color="black" />
                    </Button>
                    <Button className="size-[40px] cursor-pointer rounded-full bg-gray-200 hover:bg-gray-300">
                        <BsFillGrid3X3GapFill color="black" />
                    </Button>
                    <Button className="size-[40px] cursor-pointer rounded-full bg-sky-500 hover:bg-sky-600">
                        <span className="text-[16px] text-white"> M </span>
                    </Button>
                </div>
            </div>
        </header>
    );
}
