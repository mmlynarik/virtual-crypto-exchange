import "server-only";

export const BACKEND_API_URL = process.env.BACKEND_API_URL;

export const GITHUB_CLIENT_ID = process.env.GITHUB_CLIENT_ID;
export const GITHUB_REDIRECT_URL = process.env.GITHUB_REDIRECT_URL;
export const GITHUB_AUTHORIZE_URL = `https://github.com/login/oauth/authorize?client_id=${GITHUB_CLIENT_ID}&redirect_uri=${GITHUB_REDIRECT_URL}&scope=user:email`;
