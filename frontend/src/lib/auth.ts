import { betterAuth } from "better-auth";
import Database from "better-sqlite3";
import { jwt } from "better-auth/plugins";

export const auth = betterAuth({
    database: new Database("better-auth.db"),
    secret: process.env.BETTER_AUTH_SECRET,
    baseURL: process.env.BETTER_AUTH_URL || "http://localhost:3000",
    emailAndPassword: {
        enabled: true,
    },
    plugins: [
        jwt({
            jwks: { keyPairConfig: { alg: "RS256" } },
            jwt: {
                issuer: process.env.BETTER_AUTH_URL || "http://localhost:3000",
                audience: process.env.BETTER_AUTH_URL || "http://localhost:3000",
                definePayload: ({ user }) => ({
                    email: user.email,
                    name: user.name,
                }),
            },
        }),
    ],
});
