import Link from "next/link";

import { PageHeader } from "../components/app-shell";

export default function Dashboard() {
  return (
    <>
      <PageHeader eyebrow="Today" title="Your search, in one calm place">
        <Link className="button primary" href="/watches">Create a Watch</Link>
      </PageHeader>
      <section className="summary" aria-label="Search summary">
        <div><p className="metric">New</p><p>Review deterministic matches in your Inbox.</p></div>
        <div><p className="metric">Daily</p><p>Your active Watches run at your chosen time.</p></div>
        <div><p className="metric">Yours</p><p>You control every application and profile change.</p></div>
      </section>
      <section className="card-grid" aria-label="Common tasks">
        <Link className="feature-card" href="/inbox">
          <span className="card-index">01</span>
          <h2>Review new jobs</h2>
          <p>See why each role matched before any optional profile comparison.</p>
          <span className="card-cta">Open Inbox →</span>
        </Link>
        <Link className="feature-card" href="/analyze">
          <span className="card-index">02</span>
          <h2>Analyze one job</h2>
          <p>Use a public URL or keep pasted text private.</p>
          <span className="card-cta">Analyze a role →</span>
        </Link>
        <Link className="feature-card" href="/applications">
          <span className="card-index">03</span>
          <h2>Track applications</h2>
          <p>Record status, notes, interviews, and reminders on your terms.</p>
          <span className="card-cta">View pipeline →</span>
        </Link>
      </section>
    </>
  );
}
