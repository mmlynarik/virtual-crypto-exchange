import {
    BACKEND_API_URL,
    GITHUB_CLIENT_ID,
    GITHUB_CLIENT_SECRET,
    GITHUB_TOKEN_URL,
    GITHUB_USER_URL,
} from "@/config";
import {generateSalt, hashPassword} from "@/lib/auth/passwordHasher";
import {SignUpSchema} from "@/lib/schemas/signup";
import "server-only";

type UserCreated = {
    id: number;
};

type User = {
    id: number;
    email: string;
    password: string;
    salt: string;
    github_id: string;
    github_name: string;
};

type GithubUser = {
    id: number;
    name: string;
};

export async function registerUserOnSignUp(parsedForm: SignUpSchema): Promise<UserCreated> {
    const salt = generateSalt();
    const hashedPassword = await hashPassword(parsedForm.password, salt);

    const payload = JSON.stringify({email: parsedForm.email, password: hashedPassword, salt: salt});
    const res = await fetch(`${BACKEND_API_URL}/users/email`, {
        method: "POST",
        body: payload,
        headers: {"Content-Type": "application/json"},
    });
    return await res.json();
}

export async function getUserByEmail(email: string): Promise<User | null> {
    const res = await fetch(`${BACKEND_API_URL}/users/email/${email}`);
    if (!res.ok) {
        return null;
    }
    return await res.json();
}

async function getGithubAccessToken(code: string): Promise<string> {
    if (!GITHUB_CLIENT_ID) {
        throw new Error("Missing GITHUB_CLIENT_ID env variable");
    }
    if (!GITHUB_CLIENT_SECRET) {
        throw new Error("Missing GITHUB_CLIENT_SECRET env variable");
    }

    const payload = {
        client_id: GITHUB_CLIENT_ID,
        client_secret: GITHUB_CLIENT_SECRET,
        code,
    };
    const queryParams = new URLSearchParams(payload).toString();
    const res = await fetch(`${GITHUB_TOKEN_URL}?${queryParams}`, {
        method: "POST",
        headers: {Accept: "application/json"},
    });
    const data = await res.json();
    return data.access_token;
}

async function getGithubUserFromToken(access_token: string): Promise<GithubUser> {
    const res = await fetch(GITHUB_USER_URL, {
        headers: {Authorization: `Bearer ${access_token}`},
    });
    return await res.json();
}

export async function getGithubUser(code: string): Promise<GithubUser> {
    const access_token = await getGithubAccessToken(code);
    const user = await getGithubUserFromToken(access_token);
    return user;
}

export async function getUserByGithubId(githubId: number): Promise<User | null> {
    const res = await fetch(`${BACKEND_API_URL}/users/github/${githubId}`);
    if (!res.ok) {
        return null;
    }
    return await res.json();
}

export async function getUserById(id: number): Promise<User | null> {
    const res = await fetch(`${BACKEND_API_URL}/users/id/${id}`);
    if (!res.ok) {
        return null;
    }
    return await res.json();
}

export async function registerUserOnGithubLogin(githubUser: GithubUser): Promise<UserCreated> {
    const payload = JSON.stringify({github_id: githubUser.id, github_name: githubUser.name});
    const res = await fetch(`${BACKEND_API_URL}/users/github`, {
        method: "POST",
        body: payload,
        headers: {"Content-Type": "application/json"},
    });
    return await res.json();
}
