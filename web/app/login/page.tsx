import { GoogleButton } from "@/components/programme/GoogleButton";
import Link from "next/link";

export default function LoginPage() {
  return (
    <div className="page">
      <div className="max-w-[420px] mx-auto mt-16 text-center">
        <Link href="/" className="wordmark">
          FPL<em>Bud</em>
          <span className="dot">.</span>
        </Link>
        <h2 className="mt-8">Sign in to ask about your team</h2>
        <div className="mt-6">
          <GoogleButton />
        </div>
        <p className="caption mt-4">
          We never ask for your FPL password. Google sign-in keeps this squad on the assistant.
        </p>
      </div>
    </div>
  );
}
