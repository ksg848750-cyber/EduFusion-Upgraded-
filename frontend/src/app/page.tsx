"use client";
import { useState } from "react";
import { authClient } from "@/lib/auth-client";

export default function Home() {
  const [email, setEmail] = useState("");
  const [name, setName] = useState("");
  const [password, setPassword] = useState("");
  
  const { data: session } = authClient.useSession();
  
  const handleSignUp = async () => {
    const { data, error } = await authClient.signUp.email({
        email,
        password,
        name
    });
    if (error) alert(error.message);
  };

  const handleSignIn = async () => {
    const { data, error } = await authClient.signIn.email({
        email,
        password,
    });
    if (error) alert(error.message);
  };
  
  const handleSignOut = async () => {
    await authClient.signOut();
  }

  return (
    <main className="p-8">
      <h1 className="text-2xl font-bold mb-4">EduFusion Better Auth Demo</h1>
      {session ? (
        <div>
          <p>Logged in as {session.user.email}</p>
          <button onClick={handleSignOut} className="bg-red-500 text-white p-2 rounded mt-2">Sign Out</button>
        </div>
      ) : (
        <div className="flex flex-col gap-4 max-w-sm">
          <input className="border p-2 text-black" placeholder="Name" value={name} onChange={e => setName(e.target.value)} />
          <input className="border p-2 text-black" placeholder="Email" value={email} onChange={e => setEmail(e.target.value)} />
          <input className="border p-2 text-black" placeholder="Password" type="password" value={password} onChange={e => setPassword(e.target.value)} />
          <div className="flex gap-2">
            <button onClick={handleSignUp} className="bg-blue-500 text-white p-2 rounded flex-1">Sign Up</button>
            <button onClick={handleSignIn} className="bg-green-500 text-white p-2 rounded flex-1">Sign In</button>
          </div>
        </div>
      )}
    </main>
  );
}
