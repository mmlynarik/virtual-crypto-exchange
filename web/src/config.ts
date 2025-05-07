import "server-only";

export const BACKEND_API_URL = process.env.BACKEND_API_URL;

export const JWT_SECRET_KEY = process.env.JWT_SECRET_KEY;
export const JWT_AUDIENCE = "vce"
export const JWT_ACCESS_TOKEN_EXPIRY_SECONDS = 5 * 60
export const JWT_REFRESH_TOKEN_EXPIRY_SECONDS = 7 * 24 * 60 * 60
export const JWT_REFRESH_IF_LESS_THAN = 60 * 60

export const GITHUB_CLIENT_ID = process.env.GITHUB_CLIENT_ID
export const GITHUB_CLIENT_SECRET = process.env.GITHUB_CLIENT_SECRET
export const GITHUB_REDIRECT_URL = process.env.GITHUB_REDIRECT_URL
export const GITHUB_TOKEN_URL = "https://github.com/login/oauth/access_token"
export const GITHUB_USER_URL = "https://api.github.com/user"
export const GITHUB_AUTHORIZE_URL = `https://github.com/login/oauth/authorize?client_id=${GITHUB_CLIENT_ID}&redirect_url=${GITHUB_REDIRECT_URL}&scope=user:email`;
