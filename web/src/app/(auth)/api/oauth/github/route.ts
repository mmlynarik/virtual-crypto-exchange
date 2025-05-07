import {createJWTSession, setJWTSessionHeader} from "@/lib/auth/jwtSession";
import {getGithubUser, getUserByGithubId, registerUserOnGithubLogin} from "@/lib/auth/user";
import {redirect} from "next/navigation";
import {type NextRequest} from "next/server";

export async function GET(request: NextRequest) {
    const queryParams = request.nextUrl.searchParams;
    const code = queryParams.get("code")!;

    let user;
    const githubUser = await getGithubUser(code);
    user = await getUserByGithubId(githubUser.id);
    if (!user) {
        user = await registerUserOnGithubLogin(githubUser);
    }
    const {accessToken, refreshToken} = await createJWTSession(user.id);
    await setJWTSessionHeader(accessToken, refreshToken);
    console.log(`User with id=${user.id} logged in`);

    redirect("/dashboard");
}
