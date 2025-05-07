import Link from "next/link";
import Image from "next/image";

export default function NextImageLink() {
    return (
        <Link href="https://nextjs.org/" className="flex items-center gap-3">
            Powered by
            <Image
                className="dark:invert"
                src="/nextjs-icon.svg"
                alt="Next.js logo"
                width={32}
                height={32}
                priority
            />
        </Link>
    );
}
