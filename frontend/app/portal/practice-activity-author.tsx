"use client";

import { FormEvent, useState } from "react";
import { Plan, Sign, request } from "../api";

export function PracticeActivityAuthor({ institutionId, plans, signs, onCreated }: {
  institutionId: number; plans: Plan[]; signs: Sign[]; onCreated: () => void;
}) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const validatedPlans = plans.filter((plan) => plan.status === "validated");
  const validatedSigns = signs.filter((sign) => sign.status === "validated");

  async function create(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    const data = new FormData(form);
    setBusy(true); setError(""); setNotice("");
    try {
      const result = await request<{ id: number }>(`/portal/${institutionId}/activities`, {
        method: "POST", body: JSON.stringify({ plan_id: Number(data.get("plan")), sign_id: Number(data.get("sign")) }),
      });
      setNotice(`Practice activity ${result.id} created. Assign it to a cohort below.`);
      form.reset();
      onCreated();
    } catch (reason) { setError(reason instanceof Error ? reason.message : "Activity creation failed."); }
    finally { setBusy(false); }
  }

  return <section className="detail-section" aria-label="Practice activity authoring">
    <h2>Create a practice activity</h2>
    <p className="quiet-copy">Connect validated vocabulary for manual, synthetic practice. Consent is required; model and schema retain the existing scaffold defaults.</p>
    {error && <p role="alert" className="alert alert--error">{error}</p>}
    {notice && <p role="status" className="alert alert--success">{notice}</p>}
    {!validatedPlans.length || !validatedSigns.length ? <p>Validate a plan and a sign before creating an activity.</p> : <form className="form-stack" onSubmit={create}>
      <label className="form-field"><span className="field-label">Validated plan</span><select name="plan" required defaultValue=""><option value="" disabled>Choose a plan</option>{validatedPlans.map((plan) => <option key={plan.id} value={plan.id}>{plan.code}</option>)}</select></label>
      <label className="form-field"><span className="field-label">Validated sign</span><select name="sign" required defaultValue=""><option value="" disabled>Choose a sign</option>{validatedSigns.map((sign) => <option key={sign.id} value={sign.id}>{sign.gloss}</option>)}</select></label>
      <button className="button button--primary" disabled={busy}>{busy ? "Creating…" : "Create activity"}</button>
    </form>}
  </section>;
}
