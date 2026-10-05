"use client";

import { FormEvent, useEffect, useState } from "react";
import Link from "next/link";

import { ApiError, BillingStatus, billingLabel, refreshCsrf, request } from "../api";

const sections = [
  ["Institutions", "Workspace registry and tenant status. Full management remains behind the protected platform boundary."],
  ["Users & Memberships", "Provisioning and role review are reserved for platform staff; no user list is exposed here yet."],
  ["Content Operations", "Vocabulary operations will grow from the existing company portal workbench."],
  ["Audit", "Append-only operational history is available to authorized backend paths; this view is not implemented yet."],
  ["Billing Status", "Read-only billing status. Checkout and entitlement changes are handled by verified backend Stripe events."],
];

export default function BackofficePage() {
  const [boundary, setBoundary] = useState<"loading" | "authorized" | "anonymous" | "denied" | "error">("loading");
  const [billing, setBilling] = useState<BillingStatus | null>(null);
  const [attempt, setAttempt] = useState(0);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    let active = true;
    request<{ billing: BillingStatus }>("/web/backoffice/boundary")
      .then((response) => { if (active) { setBilling(response.billing); setBoundary("authorized"); } })
      .catch((error: unknown) => {
        if (!active) return;
        setBoundary(error instanceof ApiError && error.status === 401 ? "anonymous" : error instanceof ApiError && error.status === 403 ? "denied" : "error");
      });
    return () => { active = false; };
  }, [attempt]);

  async function login(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    setBusy(true); setError("");
    try {
      await refreshCsrf();
      await request("/web/login", { method: "POST", body: JSON.stringify({ email: form.get("email"), password: form.get("password") }) });
      setBoundary("loading"); setAttempt((value) => value + 1);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Sign in failed. Try again.");
    } finally { setBusy(false); }
  }

  async function logout() {
    setBusy(true); setError("");
    try {
      await refreshCsrf();
      await request("/web/logout", { method: "POST" });
      setBilling(null); setBoundary("anonymous");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Sign out failed. Try again.");
    } finally { setBusy(false); }
  }

  if (boundary === "loading") {
    return <main className="gate"><p role="status">Checking platform staff access…</p></main>;
  }

  if (boundary !== "authorized") {
    return (
      <main className="gate">
        <Link className="brand" href="/"><span className="brand__mark">DS</span><span className="brand__text"><strong>DualSign</strong><span>INTERNAL BACKOFFICE</span></span></Link>
        <h1>{boundary === "anonymous" ? "Sign in to the internal backoffice" : boundary === "denied" ? "Platform staff access required" : "Backoffice unavailable"}</h1>
        <p className="subtle">{boundary === "anonymous" ? "Use your authorized DualSign staff account." : boundary === "denied" ? "This surface is reserved for authorized DualSign staff." : "The protected access check could not be completed."}</p>
        {error && <p className="alert alert--error" role="alert">{error}</p>}
        {boundary === "anonymous" && <form className="form-stack login-form" onSubmit={login}>
          <label className="form-field"><span className="field-label">Email</span><input name="email" type="email" autoComplete="username" required /></label>
          <label className="form-field"><span className="field-label">Password</span><input name="password" type="password" autoComplete="current-password" required /></label>
          <button className="button button--primary" disabled={busy}>{busy ? "Signing in…" : "Sign in"}</button>
        </form>}
        {boundary === "denied" && <button className="button button--secondary" disabled={busy} onClick={() => void logout()}>Sign out and use another account</button>}
        {boundary === "error" && <button className="button button--secondary" onClick={() => { setBoundary("loading"); setAttempt((value) => value + 1); }}>Retry access check</button>}
        <Link className="button button--quiet" href="/">Return to product surfaces</Link>
      </main>
    );
  }

  return (
    <main className="backoffice-shell">
      <header className="surface-header">
        <Link className="brand" href="/"><span className="brand__mark">DS</span><span className="brand__text"><strong>DualSign</strong><span>INTERNAL BACKOFFICE</span></span></Link>
        <Link className="button button--quiet" href="/portal">Company portal</Link>
        <button className="button button--quiet" disabled={busy} onClick={() => void logout()}>Sign out</button>
      </header>
      {error && <p className="alert alert--error" role="alert">{error}</p>}
      <section className="backoffice-intro">
        <p className="kicker">PLATFORM OPERATIONS</p>
        <h1>Internal DualSign backoffice</h1>
        <p className="subtle">A staff-only shell for operating the product. Enterprise management is intentionally not claimed by this first slice.</p>
      </section>
      <div className="backoffice-grid">
         {sections.map(([title, description]) => <article className="backoffice-card" key={title}><p className="kicker">INTERNAL AREA</p><h2>{title}</h2><p>{title === "Billing Status" && billing ? `${billingLabel(billing.origin)} · ${billing.subscription_status ?? "No active subscription"}` : description}</p><span className="status-chip">{title === "Billing Status" ? "Read-only" : "Coming later"}</span></article>)}
      </div>
    </main>
  );
}
