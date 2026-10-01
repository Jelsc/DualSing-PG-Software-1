"use client";

import { useEffect, useState } from "react";
import Link from "next/link";

import { ApiError, BillingStatus, billingLabel, request } from "../api";

const sections = [
  ["Institutions", "Workspace registry and tenant status. Full management remains behind the protected platform boundary."],
  ["Users & Memberships", "Provisioning and role review are reserved for platform staff; no user list is exposed here yet."],
  ["Content Operations", "Vocabulary operations will grow from the existing company portal workbench."],
  ["Audit", "Append-only operational history is available to authorized backend paths; this view is not implemented yet."],
  ["Billing Status", "Read-only billing status. Checkout and entitlement changes are handled by verified backend Stripe events."],
];

export default function BackofficePage() {
  const [boundary, setBoundary] = useState<"loading" | "authorized" | "denied" | "error">("loading");
  const [billing, setBilling] = useState<BillingStatus | null>(null);

  useEffect(() => {
    let active = true;
    request<{ billing: BillingStatus }>("/web/backoffice/boundary")
      .then((response) => { if (active) { setBilling(response.billing); setBoundary("authorized"); } })
      .catch((error: unknown) => {
        if (!active) return;
        setBoundary(error instanceof ApiError && error.status === 403 ? "denied" : "error");
      });
    return () => { active = false; };
  }, []);

  if (boundary === "loading") {
    return <main className="gate"><p role="status">Checking platform staff access…</p></main>;
  }

  if (boundary !== "authorized") {
    return (
      <main className="gate">
        <Link className="brand" href="/"><span className="brand__mark">DS</span><span className="brand__text"><strong>DualSign</strong><span>INTERNAL BACKOFFICE</span></span></Link>
        <h1>{boundary === "denied" ? "Platform staff access required" : "Backoffice unavailable"}</h1>
        <p className="subtle">{boundary === "denied" ? "This surface is reserved for authorized DualSign staff." : "The protected access check could not be completed."}</p>
        <Link className="button button--quiet" href="/">Return to product surfaces</Link>
      </main>
    );
  }

  return (
    <main className="backoffice-shell">
      <header className="surface-header">
        <Link className="brand" href="/"><span className="brand__mark">DS</span><span className="brand__text"><strong>DualSign</strong><span>INTERNAL BACKOFFICE</span></span></Link>
        <Link className="button button--quiet" href="/portal">Company portal</Link>
      </header>
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
