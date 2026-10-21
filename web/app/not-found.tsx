import Link from "next/link";

export default function NotFound() {
  return (
    <div className="page">
      <p className="kicker mt-24">Correction</p>
      <h1 className="mt-2">That page isn&apos;t in this edition.</h1>
      <Link href="/" className="btn btn-primary mt-6 inline-flex">
        Back to the front page
      </Link>
    </div>
  );
}
