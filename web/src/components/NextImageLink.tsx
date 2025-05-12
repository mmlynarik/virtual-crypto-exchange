import Image from "next/image";
import Link from "next/link";

export default function NextImageLink() {
    return (
        <Link href="https://nextjs.org/" className="flex items-center gap-3">
            Powered by
            <Image
                className="dark:invert"
                src="/next-js.png"
                alt="Next.js logo"
                width={32}
                height={32}
                priority
            />
        </Link>
    );
}
