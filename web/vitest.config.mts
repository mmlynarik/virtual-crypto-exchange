import {fileURLToPath} from "node:url";
import {defineConfig} from "vitest/config";

export default defineConfig({
    resolve: {
        alias: {
            "@": fileURLToPath(new URL("./src", import.meta.url)),
            // The real package throws when imported outside a Next.js server build
            "server-only": fileURLToPath(new URL("./test/empty.ts", import.meta.url)),
        },
    },
    test: {
        environment: "node",
        // Read by src/config.ts when it is first imported; tests mock fetch, so nothing is sent there
        env: {BACKEND_API_URL: "http://backend.test"},
        include: ["src/**/*.test.ts"],
    },
});
