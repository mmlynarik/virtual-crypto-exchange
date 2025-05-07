import crypto from "crypto";
import "server-only";

export async function hashPassword(password: string, salt: string): Promise<string> {
    return new Promise((resolve, reject) => {
        crypto.scrypt(password.normalize(), salt, 64, (error, hash) => {
            if (error) {
                reject(error);
            }
            resolve(hash.toString("hex"));
        });
    });
}

export function generateSalt() {
    return crypto.randomBytes(16).toString("hex");
}

export async function verifyPassword(password: string, hashedPassword: string, salt: string) {
    const inputHashed = await hashPassword(password, salt);
    return crypto.timingSafeEqual(Buffer.from(inputHashed, "hex"), Buffer.from(hashedPassword, "hex"));
}
