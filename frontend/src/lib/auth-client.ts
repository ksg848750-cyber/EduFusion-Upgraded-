import { createAuthClient } from "better-auth/react";
import { jwtClient } from "better-auth/client/plugins";

export const authClient = createAuthClient({
    baseURL: process.env.NEXT_PUBLIC_BETTER_AUTH_URL || "http://localhost:3000",
    plugins: [jwtClient()],
});

export async function fetchBackendProfile() {
    const { data, error } = await authClient.token();
    if (error || !data?.token) {
        throw new Error(error?.message || "Unable to retrieve an authentication token.");
    }

    const response = await fetch(
        `${process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"}/api/v1/auth/me`,
        { headers: { Authorization: `Bearer ${data.token}` } },
    );

    if (!response.ok) {
        throw new Error("The API could not verify your authentication token.");
    }

    return response.json();
}
