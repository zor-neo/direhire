import Link from "next/link";

import { apiLoginUrl, apiSignupUrl } from "./lib/api";

const discoverySteps = [
  ["01", "Describe your search", "Create focused Job Watches with target, required, and excluded terms."],
  ["02", "Let DireHire discover", "Combine live sources, employer ATS boards, and safe external-search handoffs."],
  ["03", "Decide with context", "Review structured job analysis, then save and track applications yourself."],
];

export default function LandingPage() {
  return (
    <>
      <header className="landing-header">
        <Link className="brand" href="/" aria-label="DireHire home">
          <span className="brand-mark" aria-hidden="true">D</span> DireHire
        </Link>
        <nav aria-label="Landing navigation">
          <a href="#how-it-works">How it works</a>
          <a href="#privacy">Privacy</a>
          <a className="button" href={apiLoginUrl()}>Sign in</a>
        </nav>
      </header>

      <main id="main" className="landing-main">
        <section className="landing-hero">
          <div className="landing-hero-copy">
            <p className="eyebrow">A calmer way to search</p>
            <h1>Find relevant work without turning job search into a full-time job.</h1>
            <p className="landing-lead">
              DireHire discovers roles from responsible sources, explains why they match your intent,
              and keeps your applications organized—without requiring a CV or professional profile.
            </p>
            <div className="landing-actions">
              <a className="button primary" href={apiSignupUrl()}>Create your account</a>
              <a className="button" href={apiLoginUrl()}>Sign in</a>
            </div>
            <p className="landing-note">Your workspace and job-search data are available only after sign-in.</p>
          </div>
          <div className="landing-preview" aria-label="DireHire workflow preview">
            <span className="preview-label">Your daily search</span>
            <div className="preview-row"><span className="preview-status live">Live</span><strong>Thailand product roles</strong><small>JobThai + employer boards</small></div>
            <div className="preview-row"><span className="preview-status">Remote</span><strong>Global engineering roles</strong><small>Remotive + ATS sources</small></div>
            <div className="preview-result"><strong>New matches stay visible</strong><span>AI can explain and rank, but your Watch intent remains in control.</span></div>
          </div>
        </section>

        <section className="landing-section" id="how-it-works">
          <p className="eyebrow">How it works</p>
          <h2>From search intent to a useful inbox.</h2>
          <div className="landing-steps">
            {discoverySteps.map(([number, title, copy]) => (
              <article key={number}>
                <span>{number}</span>
                <h3>{title}</h3>
                <p>{copy}</p>
              </article>
            ))}
          </div>
        </section>

        <section className="landing-section landing-split">
          <div>
            <p className="eyebrow">Responsible coverage</p>
            <h2>Useful sources, with honest limits.</h2>
          </div>
          <p>
            Live discovery currently focuses on JobThai, Remotive, USAJOBS when configured, and public
            employer ATS boards. Restricted regional sites open as external searches instead of using
            account credentials, CAPTCHA bypasses, or hidden access.
          </p>
        </section>

        <section className="landing-section landing-split" id="privacy">
          <div>
            <p className="eyebrow">Private by design</p>
            <h2>Your career data is not an admin browsing surface.</h2>
          </div>
          <p>
            Public job data can be reused safely. Pasted job descriptions, profiles, CVs, notes, and
            application history remain private, with authenticated access and user-controlled changes.
          </p>
        </section>

        <section className="landing-cta">
          <div><p className="eyebrow">Ready when you are</p><h2>Start with one focused Job Watch.</h2></div>
          <a className="button primary" href={apiSignupUrl()}>Create your account</a>
        </section>
      </main>

      <footer className="landing-footer">
        <span>DireHire</span>
        <span>Calm, responsible job discovery.</span>
      </footer>
    </>
  );
}
