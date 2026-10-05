"use client";

import { FormEvent, useCallback, useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";
import { PracticeActivityAuthor } from "./practice-activity-author";
import {
  Alias,
  ApiError,
  BillingStatus,
  Catalog,
  CohortAssignment,
  Cohort,
  CohortDetail,
  CohortProgress,
  CohortStatus,
  Concept,
  Membership,
  PortalMember,
  PortalParticipant,
  Plan,
  Sign,
  Status,
  User,
  Variant,
  billingLabel,
  loadCatalog,
  refreshCsrf,
  request,
  statusLabel,
} from "../api";

type Section = "concepts" | "signs" | "plans" | "cohorts";
type Notice = { kind: "error" | "success"; text: string };
const emptyCatalog: Catalog = { concepts: [], aliases: [], signs: [], plans: [] };
const canManage = (role: string) =>
  role === "institution_admin" || role === "vocabulary_reviewer";

function messageFor(error: unknown) {
  return error instanceof Error ? error.message : "The request could not be completed.";
}

function useRequestScope(key: string | number) {
  const token = useMemo(() => ({ key }), [key]);
  const scope = useRef<typeof token | null>(token);
  useEffect(() => {
    scope.current = token;
    return () => { scope.current = null; };
  }, [token]);
  return useCallback(() => scope.current === token, [token]);
}

export default function Home() {
  const [user, setUser] = useState<User | null>(null);
  const [memberships, setMemberships] = useState<Membership[]>([]);
  const [institutionId, setInstitutionId] = useState<number | "">("");
  const [section, setSection] = useState<Section>("concepts");
  const [catalog, setCatalog] = useState<Catalog>(emptyCatalog);
  const [loading, setLoading] = useState(true);
  const [catalogLoading, setCatalogLoading] = useState(false);
  const [bootError, setBootError] = useState("");
  const [notice, setNotice] = useState<Notice | null>(null);
  const [query, setQuery] = useState("");
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [editing, setEditing] = useState(false);
  const [busy, setBusy] = useState(false);
  const [variants, setVariants] = useState<Variant[]>([]);
  const [loginError, setLoginError] = useState("");
  const [billing, setBilling] = useState<BillingStatus | null>(null);
  const [billingBusy, setBillingBusy] = useState(false);
  const catalogGeneration = useRef(0);
  const [cohortRevision, setCohortRevision] = useState(0);
  const institutionScope = useRequestScope(institutionId);
  const recordScope = useRequestScope(`${institutionId}-${section}-${selectedId}`);
  const refreshCohortPanels = useCallback(() => setCohortRevision((value) => value + 1), []);

  const boot = useCallback(async () => {
    try {
      await refreshCsrf();
      const session = await request<{ user: User; memberships: Membership[] }>("/web/me");
      setBootError("");
      setUser(session.user);
      setMemberships(session.memberships.filter((membership) => canManage(membership.role)));
      setInstitutionId("");
    } catch (error) {
      if (error instanceof ApiError && error.status === 401) {
        setUser(null);
      } else {
        setBootError(messageFor(error));
      }
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    let active = true;
    refreshCsrf()
      .then(() => request<{ user: User; memberships: Membership[] }>("/web/me"))
      .then((session) => {
        if (!active) return;
        setUser(session.user);
        setMemberships(session.memberships.filter((membership) => canManage(membership.role)));
        setBootError("");
      })
      .catch((error: unknown) => {
        if (!active) return;
        if (!(error instanceof ApiError && error.status === 401)) {
          setBootError(messageFor(error));
        }
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, []);

  const refreshCatalog = useCallback(async (id: number) => {
    const generation = ++catalogGeneration.current;
    setCatalogLoading(true);
    setNotice(null);
    try {
      const data = await loadCatalog(id);
      if (generation !== catalogGeneration.current) return;
      setCatalog(data);
      setEditing(false);
    } catch (error) {
      if (generation !== catalogGeneration.current) return;
      setCatalog(emptyCatalog);
      setBilling(null);
      setNotice({ kind: "error", text: messageFor(error) });
    } finally {
      if (generation === catalogGeneration.current) setCatalogLoading(false);
    }
  }, []);

  useEffect(() => {
    if (section !== "signs" || institutionId === "" || selectedId === null) return;
    let active = true;
    request<Variant[]>(`/vocabulary/${institutionId}/signs/${selectedId}/variants`)
      .then((items) => { if (active) setVariants(items); })
      .catch((error: unknown) => { if (active) setNotice({ kind: "error", text: messageFor(error) }); });
    return () => { active = false; };
  }, [institutionId, section, selectedId]);

  useEffect(() => {
    if (institutionId === "") {
      return;
    }
    let active = true;
    request<BillingStatus>(`/billing/enterprise/${institutionId}/status`)
      .then((status) => { if (active) setBilling(status); })
      .catch((error: unknown) => { if (active) setNotice({ kind: "error", text: messageFor(error) }); });
    return () => { active = false; };
  }, [institutionId]);

  const membershipsAvailable = memberships.length > 0;
  const records = useMemo(() => section === "cohorts" ? [] : catalog[section], [catalog, section]);
  const filteredRecords = useMemo(() => {
    const needle = query.trim().toLocaleLowerCase();
    if (!needle) return records;
    return records.filter((record) => {
      const searchable =
        section === "concepts"
          ? `${(record as Concept).code} ${(record as Concept).label}`
          : section === "signs"
            ? `${(record as Sign).sign_id} ${(record as Sign).gloss}`
            : `${(record as Plan).code} ${(record as Plan).items.map((item) => item.gloss).join(" ")}`;
      return searchable.toLocaleLowerCase().includes(needle);
    });
  }, [query, records, section]);

  const selected = records.find((record) => record.id === selectedId) ?? null;
  const institution = memberships.find((item) => item.institution_id === institutionId);
  const aliasesForConcept = (id: number) => catalog.aliases.filter((alias) => alias.concept_id === id);

  async function refreshAfterWrite(success: string) {
    if (institutionId === "" || !institutionScope()) return;
    setNotice({ kind: "success", text: success });
    setEditing(false);
    await refreshCatalog(institutionId);
    if (!institutionScope()) return;
    setNotice({ kind: "success", text: success });
  }

  async function startEnterpriseCheckout() {
    if (institutionId === "") return;
    setBillingBusy(true);
    setNotice(null);
    try {
      const result = await request<{ checkout_url: string }>(`/billing/enterprise/${institutionId}/checkout`, { method: "POST" });
      window.location.assign(result.checkout_url);
    } catch (error) {
      setNotice({ kind: "error", text: messageFor(error) });
    } finally {
      setBillingBusy(false);
    }
  }

  async function perform(action: () => Promise<unknown>, success: string) {
    setBusy(true);
    setNotice(null);
    try {
      await action();
      if (!institutionScope()) return;
      await refreshAfterWrite(success);
    } catch (error) {
      if (institutionScope()) setNotice({ kind: "error", text: messageFor(error) });
    } finally {
      if (institutionScope()) setBusy(false);
    }
  }

  async function login(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setLoginError("");
    setBusy(true);
    const form = new FormData(event.currentTarget);
    try {
      await refreshCsrf();
      await request("/web/login", {
        method: "POST",
        body: JSON.stringify({
          email: String(form.get("email") ?? ""),
          password: String(form.get("password") ?? ""),
        }),
      });
      setLoading(true);
      await boot();
    } catch (error) {
      setLoading(false);
      setLoginError(messageFor(error));
    } finally {
      setBusy(false);
    }
  }

  async function logout() {
    setBusy(true);
    setNotice(null);
    try {
      await request("/web/logout", { method: "POST" });
      catalogGeneration.current++;
      setUser(null);
      setMemberships([]);
      setInstitutionId("");
      setCatalog(emptyCatalog);
    } catch (error) {
      setNotice({ kind: "error", text: messageFor(error) });
    } finally {
      setBusy(false);
    }
  }

  async function removeRecord() {
    if (!selected || institutionId === "") return;
    const path = section === "concepts" ? "concepts" : section;
    const id = selected.id;
    await perform(
      () => request(`/vocabulary/${institutionId}/${path}/${id}`, { method: "DELETE" }),
      `${section.slice(0, -1)} deleted.`,
    );
  }

  async function transition(action: "review" | "validate" | "reject" | "reopen") {
    if (!selected || institutionId === "" || section === "concepts") return;
    const route = section === "signs" ? "signs" : "plans";
    await perform(
      () =>
        request(`/vocabulary/${institutionId}/${route}/${selected.id}/${action}`, {
          method: "POST",
        }),
      `${section === "signs" ? "Sign" : "Plan"} ${{
        review: "sent for review",
        validate: "validated",
        reject: "rejected",
        reopen: "reopened as draft",
      }[action]}.`,
    );
  }

  async function submitConcept(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (institutionId === "") return;
    const form = new FormData(event.currentTarget);
    const payload = {
      code: String(form.get("code") ?? "").trim(),
      label: String(form.get("label") ?? "").trim(),
      description: String(form.get("description") ?? "").trim(),
    };
    const path = `/vocabulary/${institutionId}/concepts`;
    await perform(
      () =>
        request(selectedId ? `${path}/${selectedId}` : path, {
          method: selectedId ? "PATCH" : "POST",
          body: JSON.stringify(selectedId ? { label: payload.label, description: payload.description } : payload),
        }),
      selectedId ? "Concept updated." : "Concept created.",
    );
  }

  async function submitSign(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (institutionId === "") return;
    const form = new FormData(event.currentTarget);
    const payload = {
      sign_id: String(form.get("sign_id") ?? "").trim(),
      concept_id: Number(form.get("concept_id")),
      gloss: String(form.get("gloss") ?? "").trim(),
      language: String(form.get("language") ?? "lsb").trim(),
    };
    const path = `/vocabulary/${institutionId}/signs`;
    await perform(
      () =>
        request(selectedId ? `${path}/${selectedId}` : path, {
          method: selectedId ? "PATCH" : "POST",
          body: JSON.stringify(selectedId ? {
            concept_id: payload.concept_id,
            gloss: payload.gloss,
            language: payload.language,
          } : payload),
        }),
      selectedId ? "Sign updated." : "Sign created.",
    );
  }

  async function submitPlan(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (institutionId === "") return;
    const form = new FormData(event.currentTarget);
    let markers: unknown;
    try {
      markers = JSON.parse(String(form.get("markers") || "[]"));
      if (!Array.isArray(markers)) throw new Error("Markers must be a JSON array.");
    } catch {
      setNotice({ kind: "error", text: "Markers must be a valid JSON array." });
      return;
    }
    const itemIds = form.getAll("items").map(Number).sort((left, right) =>
      Number(form.get(`position-${left}`)) - Number(form.get(`position-${right}`)),
    );
    const payload = {
      code: String(form.get("code") ?? "").trim(),
      concept_id: Number(form.get("concept_id")),
      language: String(form.get("language") ?? "lsb").trim(),
      variant: String(form.get("variant") ?? "").trim(),
      non_manual_markers: markers,
      items: itemIds.map((sign_id) => {
        const variantValue = form.get(`variant-${sign_id}`);
        const previousVariant = catalog.plans
          .find((plan) => plan.id === selectedId)
          ?.items.find((item) => item.sign_id === sign_id)?.variant_id;
        return {
          sign_id,
          variant_id: variantValue === null ? previousVariant ?? null : Number(variantValue) || null,
        };
      }),
    };
    const path = `/vocabulary/${institutionId}/plans`;
    await perform(
      () =>
        request(selectedId ? `${path}/${selectedId}` : path, {
          method: selectedId ? "PATCH" : "POST",
          body: JSON.stringify(selectedId ? {
            concept_id: payload.concept_id,
            language: payload.language,
            variant: payload.variant,
            non_manual_markers: payload.non_manual_markers,
            items: payload.items,
          } : payload),
        }),
      selectedId ? "Sign plan updated." : "Sign plan created.",
    );
  }

  async function addAlias(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selected || institutionId === "") return;
    const form = new FormData(event.currentTarget);
    const alias = String(form.get("alias") ?? "").trim();
    await perform(
      () => request(`/vocabulary/${institutionId}/concepts/${selected.id}/aliases`, {
        method: "POST",
        body: JSON.stringify({ alias }),
      }),
      "Alias added.",
    );
  }

  async function editAlias(alias: Alias) {
    if (institutionId === "") return;
    const value = window.prompt("Edit alias", alias.alias);
    if (value === null || !value.trim()) return;
    await perform(
      () => request(`/vocabulary/${institutionId}/aliases/${alias.id}`, {
        method: "PATCH",
        body: JSON.stringify({ alias: value.trim() }),
      }),
      "Alias updated.",
    );
  }

  async function deleteAlias(alias: Alias) {
    if (institutionId === "") return;
    await perform(
      () => request(`/vocabulary/${institutionId}/aliases/${alias.id}`, { method: "DELETE" }),
      "Alias deleted.",
    );
  }

  async function addVariant(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selected || section !== "signs" || institutionId === "") return;
    const form = new FormData(event.currentTarget);
    const payload = {
      variant_code: String(form.get("variant_code") ?? "").trim(),
      label: String(form.get("label") ?? "").trim(),
      hamnosys: String(form.get("hamnosys") ?? "").trim(),
    };
    const formElement = event.currentTarget;
    setBusy(true);
    setNotice(null);
    try {
      const variant = await request<Variant>(`/vocabulary/${institutionId}/signs/${selected.id}/variants`, {
        method: "POST",
        body: JSON.stringify(payload),
      });
      if (!recordScope()) return;
      setVariants((current) => [variant, ...current]);
      setNotice({ kind: "success", text: "Variant added." });
      formElement.reset();
    } catch (error) {
      setNotice({ kind: "error", text: messageFor(error) });
    } finally {
      setBusy(false);
    }
  }

  async function editVariant(variant: Variant) {
    if (institutionId === "") return;
    const label = window.prompt("Variant label", variant.label);
    if (label === null) return;
    await perform(async () => {
      const updated = await request<Variant>(`/vocabulary/${institutionId}/variants/${variant.id}`, {
        method: "PATCH",
        body: JSON.stringify({
          variant_code: variant.variant_code,
          label: label.trim(),
          hamnosys: variant.hamnosys,
        }),
      });
      if (recordScope()) setVariants((current) => current.map((item) => item.id === updated.id ? updated : item));
    }, "Variant updated.");
  }

  async function deleteVariant(variant: Variant) {
    if (institutionId === "") return;
    await perform(
      () => request(`/vocabulary/${institutionId}/variants/${variant.id}`, { method: "DELETE" }),
      "Variant deleted.",
    );
  }

  const heading = section === "concepts" ? "Concepts" : section === "signs" ? "Signs" : section === "plans" ? "Sign plans" : "Pilot cohorts";

  if (loading) {
    return <main className="gate"><p role="status">Connecting to the institution workspace…</p></main>;
  }

  if (bootError) {
    return (
      <main className="gate">
        <Brand />
        <h1>Workspace unavailable</h1>
        <p className="subtle">The session service could not be reached. Your institution data has not been changed.</p>
        <p className="alert alert--error" role="alert">{bootError}</p>
        <button className="button button--primary" onClick={() => { setLoading(true); void boot(); }}>Try again</button>
      </main>
    );
  }

  if (!user) {
    return (
      <main className="gate">
        <Brand />
        <p className="kicker">INSTITUTIONAL CURATION</p>
        <h1>Sign in to your workbench</h1>
        <p className="subtle">Review and maintain the LSB vocabulary for your institution.</p>
        <form className="form-stack login-form" onSubmit={login}>
          <Field label="Email" name="email" type="email" required autoComplete="username" />
          <Field label="Password" name="password" type="password" required autoComplete="current-password" />
          {loginError && <p className="alert alert--error" role="alert">{loginError}</p>}
          <button className="button button--primary" disabled={busy}>{busy ? "Signing in…" : "Sign in"}</button>
        </form>
      </main>
    );
  }

  return (
    <div className="workbench">
      <header className="topbar">
        <Brand />
        <div className="account">
          <span className="account__email">{user.email}</span>
          <button className="button button--quiet" onClick={() => void logout()} disabled={busy}>Sign out</button>
        </div>
      </header>

      <div className="workbench-grid">
        <aside className="rail" aria-label="Vocabulary navigation">
          <div className="institution-switcher">
            <label className="field-label" htmlFor="institution">Institution</label>
            <select id="institution" value={institutionId} onChange={(event) => {
              const nextInstitutionId = event.target.value ? Number(event.target.value) : "";
              setInstitutionId(nextInstitutionId);
              catalogGeneration.current++;
              setCatalogLoading(false);
              setEditing(false);
              setBusy(false);
              setCatalog(emptyCatalog);
               setVariants([]);
               setBilling(null);
              setSelectedId(null);
              setQuery("");
              if (nextInstitutionId !== "") void refreshCatalog(nextInstitutionId);
            }}>
              <option value="">Choose an institution</option>
              {memberships.map((membership) => (
                <option key={membership.institution_id} value={membership.institution_id}>
                  {membership.institution_name}
                </option>
              ))}
            </select>
          </div>
          {membershipsAvailable ? (
            <>
              <p className="rail-label">VOCABULARY</p>
              <nav className="nav-list" aria-label="Institution workspace sections">
                {(["concepts", "signs", "plans", "cohorts"] as Section[]).map((item) => (
                  <button key={item} aria-current={section === item ? "page" : undefined} className={`nav-item ${section === item ? "is-active" : ""}`} onClick={() => {
                    setSection(item);
                    setSelectedId(null);
                    setEditing(false);
                    setQuery("");
                    setNotice(null);
                  }}>
                     <span className="nav-item__glyph" aria-hidden="true">{item === "concepts" ? "◈" : item === "signs" ? "⌁" : item === "plans" ? "≋" : "⌂"}</span>
                     <span>{item === "plans" ? "Sign plans" : item === "cohorts" ? "Pilot cohorts" : item[0].toUpperCase() + item.slice(1)}</span>
                     <span className="nav-count">{item === "cohorts" ? "→" : catalog[item].length}</span>
                  </button>
                ))}
              </nav>
              <div className="rail-note">
                <span className="rail-note__mark" aria-hidden="true">LSB</span>
                <p>Curate the shared vocabulary with care. Changes are scoped to this institution.</p>
              </div>
            </>
          ) : (
            <div className="rail-note rail-note--empty">
              <span className="rail-note__mark" aria-hidden="true">i</span>
              <p>No institution workspace is available for this account. Ask an institution administrator to grant membership.</p>
            </div>
          )}
        </aside>

        <main className="main-area">
          {!membershipsAvailable ? (
            <section className="empty-state empty-state--wide">
              <span className="empty-glyph" aria-hidden="true">⌂</span>
              <p className="kicker">NO ACTIVE MEMBERSHIPS</p>
              <h1>Institution access is unavailable</h1>
              <p>The web session does not provide an institution list for this account. This workbench can only open institutions listed in your active memberships.</p>
            </section>
          ) : institutionId === "" ? (
            <section className="welcome-panel">
              <p className="kicker">LSB VOCABULARY / CURATION DESK</p>
              <h1>Language is shaped<br />one record at a time.</h1>
              <p>Select an institution to work with its concepts, signs and sign plans. Review actions are recorded against the active institution.</p>
              <div className="welcome-rule"><span />INSTITUTIONAL SCOPE<span /></div>
            </section>
          ) : (
            <>
              <div className="page-heading">
                <div>
                  <p className="kicker">{institution?.institution_name ?? "INSTITUTION"} <span className="kicker-divider">/</span> CURATION</p>
                  <h1>{heading}</h1>
                  <p className="page-subtitle">{section === "concepts" ? "The ideas and alternate terms that anchor your vocabulary." : section === "signs" ? "Sign records, their review status and recorded variants." : section === "cohorts" ? "Manage pilot cohorts, practice activities, assignments and participation." : "Ordered sign sequences with non-manual markers and review history."}</p>
                </div>
                 {section !== "cohorts" && <button className="button button--primary create-button" onClick={() => {
                  setSelectedId(null);
                  setEditing(true);
                  setNotice(null);
                 }} disabled={catalogLoading}>
                   <span aria-hidden="true">＋</span> New {section === "plans" ? "plan" : section.slice(0, -1)}
                 </button>}
              </div>

              <section className="detail-section" aria-label="Billing status">
                <p className="section-label">BILLING STATUS</p>
                <h2>{billing ? billingLabel(billing.origin) : "Loading billing status…"}</h2>
                <p className="quiet-copy">Enterprise access is granted only after a verified Stripe webhook.</p>
                {institution?.role === "institution_admin" && billing?.origin !== "enterprise_access" && <button className="button button--secondary" onClick={() => void startEnterpriseCheckout()} disabled={billingBusy}>{billingBusy ? "Opening checkout…" : "Start enterprise checkout"}</button>}
              </section>

              {notice && <p className={`alert alert--${notice.kind}`} role={notice.kind === "error" ? "alert" : "status"}>{notice.text}</p>}

                {section === "cohorts" ? <div key={institutionId}>
                  <CohortWorkspace institutionId={institutionId as number} canManage={institution?.role === "institution_admin"} onChanged={refreshCohortPanels} />
                  {institution?.role === "institution_admin" && <PracticeActivityAuthor institutionId={institutionId as number} plans={catalog.plans} signs={catalog.signs} onCreated={refreshCohortPanels} />}
                  <CohortAssignmentPanel key={`assignment-${cohortRevision}`} institutionId={institutionId as number} canManage={institution?.role === "institution_admin"} canViewProgress={institution?.role === "institution_admin" || institution?.role === "vocabulary_reviewer"} />
                  <ParticipantRoster key={`roster-${cohortRevision}`} institutionId={institutionId as number} canManage={institution?.role === "institution_admin"} />
                </div> : <div className="catalog-layout">
                <section className="record-column" aria-label={`${heading} list`}>
                  <label className="search-field">
                    <span className="search-icon" aria-hidden="true">⌕</span>
                    <input value={query} onChange={(event) => setQuery(event.target.value)} placeholder={`Find ${heading.toLowerCase()}…`} aria-label={`Filter ${heading.toLowerCase()}`} />
                    {query && <button type="button" className="clear-search" aria-label="Clear filter" onClick={() => setQuery("")}>×</button>}
                  </label>
                  <div className="list-meta"><span>{catalogLoading ? "Refreshing records…" : `${filteredRecords.length} ${filteredRecords.length === 1 ? "record" : "records"}`}</span><span>IN THIS INSTITUTION</span></div>
                  {catalogLoading ? (
                    <div className="list-loading" role="status">Loading vocabulary…</div>
                  ) : filteredRecords.length === 0 ? (
                    <div className="list-empty"><span aria-hidden="true">⌁</span><strong>{query ? "No matching records" : `No ${heading.toLowerCase()} yet`}</strong><p>{query ? "Try a different term." : "New records will appear here after they are added."}</p></div>
                  ) : (
                    <div className="record-list">
                      {filteredRecords.map((record) => {
                        const title = section === "concepts" ? (record as Concept).label : section === "signs" ? (record as Sign).gloss : (record as Plan).code;
                        const code = section === "concepts" ? (record as Concept).code : section === "signs" ? (record as Sign).sign_id : `${(record as Plan).items.length} ordered ${(record as Plan).items.length === 1 ? "sign" : "signs"}`;
                        const status = section === "concepts" ? null : (record as Sign | Plan).status;
                        return (
                          <button key={record.id} className={`record-row ${selectedId === record.id && !editing ? "is-selected" : ""}`} onClick={() => {
                            setSelectedId(record.id);
                            setEditing(false);
                            setNotice(null);
                          }}>
                            <span className="record-row__main"><strong>{title || "Untitled record"}</strong><span>{code}</span></span>
                            {status ? <StatusBadge status={status} /> : <span className="record-arrow" aria-hidden="true">↗</span>}
                          </button>
                        );
                      })}
                    </div>
                  )}
                </section>

                <section className="detail-column" aria-label={`${heading} details`}>
                  {editing ? (
                    <RecordForm
                      key={`${institutionId}-${section}-${selectedId}`}
                      institutionId={institutionId as number}
                      section={section}
                      selected={selected}
                      concepts={catalog.concepts}
                      signs={catalog.signs}
                      variants={variants}
                      onConcept={submitConcept}
                      onSign={submitSign}
                      onPlan={submitPlan}
                      onCancel={() => setEditing(false)}
                      busy={busy}
                    />
                  ) : !selected ? (
                    <div className="detail-placeholder"><span className="detail-placeholder__glyph" aria-hidden="true">{section === "concepts" ? "◈" : section === "signs" ? "⌁" : "≋"}</span><p className="kicker">RECORD DETAIL</p><h2>Choose a record to inspect</h2><p>Its attributes, connected vocabulary and available review actions will appear here.</p></div>
                  ) : section === "concepts" ? (
                    <ConceptDetail
                      concept={selected as Concept}
                      aliases={aliasesForConcept(selected.id)}
                      onEdit={() => setEditing(true)}
                      onDelete={() => void removeRecord()}
                      onAddAlias={addAlias}
                      onEditAlias={(alias) => void editAlias(alias)}
                      onDeleteAlias={(alias) => void deleteAlias(alias)}
                      busy={busy}
                    />
                  ) : section === "signs" ? (
                    <SignDetail
                      sign={selected as Sign}
                      concept={catalog.concepts.find((concept) => concept.id === (selected as Sign).concept_id)}
                      variants={variants.filter((variant) => variant.sign_id === selected.id)}
                      canDeleteVariant={(variant) => !catalog.plans.some((plan) => plan.items.some((item) => item.variant_id === variant.id))}
                      onEdit={() => setEditing(true)}
                      onDelete={() => void removeRecord()}
                      onTransition={(action) => void transition(action)}
                      onAddVariant={addVariant}
                      onEditVariant={(variant) => void editVariant(variant)}
                      onDeleteVariant={(variant) => void deleteVariant(variant)}
                      busy={busy}
                    />
                  ) : (
                    <PlanDetail
                      plan={selected as Plan}
                      concept={catalog.concepts.find((concept) => concept.id === (selected as Plan).concept_id)}
                      onEdit={() => setEditing(true)}
                      onDelete={() => void removeRecord()}
                      onTransition={(action) => void transition(action)}
                      busy={busy}
                    />
                  )}
                </section>
              </div>}
            </>
          )}
          <footer className="main-footer"><span>DUALSIGN <span aria-hidden="true">·</span> VOCABULARY CURATION</span><span>Session-scoped access</span></footer>
        </main>
      </div>
    </div>
  );
}

function Brand() {
  return <Link className="brand" href="/" aria-label="DualSign vocabulary workbench home"><span className="brand__mark" aria-hidden="true">DS</span><span className="brand__text"><strong>DualSign</strong><span>VOCABULARY WORKBENCH</span></span></Link>;
}

function CohortWorkspace({ institutionId, canManage, onChanged }: { institutionId: number; canManage: boolean; onChanged: () => void }) {
  const scope = useRequestScope(institutionId);
  const detailGeneration = useRef(0);
  const [cohorts, setCohorts] = useState<Cohort[]>([]);
  const [selected, setSelected] = useState<CohortDetail | null>(null);
  const [editing, setEditing] = useState(false);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [detailPending, setDetailPending] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const rows = await request<Cohort[]>(`/portal/${institutionId}/cohorts`);
      if (!scope()) return;
      setCohorts(rows);
      setSelected(null);
    } catch (reason) {
      setError(messageFor(reason));
    } finally {
      setLoading(false);
    }
  }, [institutionId, scope]);

  useEffect(() => {
    const timer = window.setTimeout(() => void load(), 0);
    return () => window.clearTimeout(timer);
  }, [load]);

  async function open(cohort: Cohort) {
    const generation = ++detailGeneration.current;
    setDetailPending(true);
    setSelected(null);
    setError("");
    try {
      const detail = await request<CohortDetail>(`/portal/${institutionId}/cohorts/${cohort.id}`);
      if (!scope() || generation !== detailGeneration.current) return;
      setSelected(detail);
      setEditing(false);
    } catch (reason) { if (scope() && generation === detailGeneration.current) setError(messageFor(reason)); }
    finally { if (scope() && generation === detailGeneration.current) setDetailPending(false); }
  }

  async function save(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const generation = detailGeneration.current;
    setBusy(true);
    setError("");
    const form = new FormData(event.currentTarget);
    const payload = {
      name: String(form.get("name") ?? "").trim(),
      start_date: String(form.get("start_date") ?? ""),
      end_date: String(form.get("end_date") ?? "") || null,
      status: String(form.get("status") ?? "planned"),
      consent_required: form.get("consent_required") === "on",
      selected_plan_ids: parseIds(String(form.get("selected_plan_ids") ?? "")),
      selected_activity_ids: parseIds(String(form.get("selected_activity_ids") ?? "")),
    };
    try {
      const path = selected ? `/portal/${institutionId}/cohorts/${selected.id}` : `/portal/${institutionId}/cohorts`;
      await request<CohortDetail>(path, { method: selected ? "PATCH" : "POST", body: JSON.stringify(payload) });
      if (!scope() || generation !== detailGeneration.current) return;
      setNotice(selected ? "Cohort updated." : "Cohort created.");
      setEditing(false);
      await load();
      onChanged();
    } catch (reason) { setError(messageFor(reason)); }
    finally { setBusy(false); }
  }

  async function changeStatus(status: CohortStatus) {
    if (!selected) return;
    const generation = detailGeneration.current;
    setBusy(true);
    try {
      const updated = await request<CohortDetail>(`/portal/${institutionId}/cohorts/${selected.id}`, { method: "PATCH", body: JSON.stringify({ status }) });
      if (!scope() || generation !== detailGeneration.current) return;
      setSelected(updated);
      setCohorts((current) => current.map((cohort) => cohort.id === updated.id ? { ...cohort, ...updated } : cohort));
      setNotice(`Cohort marked ${status}.`);
      onChanged();
    } catch (reason) { setError(messageFor(reason)); }
    finally { setBusy(false); }
  }

  const selectedSummary = selected?.report;
  return <section className="cohort-workspace" aria-label="Pilot cohorts">
    <div className="cohort-heading"><div><p className="section-label">PILOT OPERATIONS</p><h2>Company pilot cohorts</h2><p className="page-subtitle">Create a controlled cohort for Flutter learners, then follow participation and synthetic practice reports.</p></div>{canManage && <button className="button button--primary" disabled={loading || busy} onClick={() => { detailGeneration.current++; setSelected(null); setEditing(true); setNotice(""); }}>＋ New cohort</button>}</div>
    {notice && <p className="alert alert--success" role="status">{notice}</p>}
    {detailPending && !editing && <p role="status">Loading cohort detail…</p>}
    {error && <p className="alert alert--error" role="alert">{error}</p>}
    {!loading && editing && cohorts.length === 0 && <CohortForm selected={null} onSubmit={save} onCancel={() => setEditing(false)} busy={busy} />}
    {!(editing && cohorts.length === 0) && <>
    {loading ? <div className="cohort-empty" role="status">Loading pilot cohorts…</div> : cohorts.length === 0 ? <div className="cohort-empty"><span aria-hidden="true">⌂</span><strong>No pilot cohorts yet</strong><p>{canManage ? "Create the first cohort for this institution." : "An institution administrator has not created a cohort yet."}</p></div> : <div className="cohort-layout"><div className="cohort-list">{cohorts.map((cohort) => <button key={cohort.id} className={`cohort-row ${selected?.id === cohort.id && !editing ? "is-selected" : ""}`} onClick={() => void open(cohort)}><span><strong>{cohort.name}</strong><small>{cohort.start_date}{cohort.end_date ? ` → ${cohort.end_date}` : " → open ended"}</small></span><CohortBadge status={cohort.status} /></button>)}</div><div className="cohort-detail">{editing ? <CohortForm selected={selected} onSubmit={save} onCancel={() => setEditing(false)} busy={busy} /> : selected ? <><div className="detail-topline"><p className="kicker">COHORT DETAIL</p><CohortBadge status={selected.status} /></div><h2 className="detail-title">{selected.name}</h2><div className="attribute-grid"><Attribute label="Window" value={`${selected.start_date} → ${selected.end_date ?? "Open ended"}`} /><Attribute label="Enrollment" value={`${selected.enrolled_count} enrolled`} /><Attribute label="Consent" value={selected.consent_required ? "Required" : "Not required"} /><Attribute label="Activities" value={String(selected.selected_activity_ids.length)} /></div>{canManage && <div className="detail-actions">{selected.status === "planned" && <button className="button button--primary" onClick={() => void changeStatus("active")} disabled={busy}>Activate cohort</button>}{selected.status === "active" && <button className="button button--danger-quiet" onClick={() => void changeStatus("closed")} disabled={busy}>Close enrollment</button>}<button className="button button--secondary" onClick={() => setEditing(true)} disabled={busy || selected.status === "closed"}>Edit cohort</button></div>}<div className="detail-section"><p className="section-label">REPORT SNAPSHOT</p>{selectedSummary ? <div className="attribute-grid"><Attribute label="Attempts" value={String(selectedSummary.attempts.total)} /><Attribute label="Unknown rate" value={`${Math.round(selectedSummary.attempts.unknown_rate * 100)}%`} /><Attribute label="Participants with attempts" value={String(selectedSummary.participation.participants_with_attempts)} /><Attribute label="Median latency" value={selectedSummary.latency_ms.p50 === null ? "—" : `${selectedSummary.latency_ms.p50} ms`} /></div> : <p className="quiet-copy">No report data is available yet.</p>}</div></> : <div className="detail-placeholder"><span className="detail-placeholder__glyph" aria-hidden="true">⌂</span><p className="kicker">COHORT DETAIL</p><h2>Choose a cohort to inspect</h2><p>Enrollment and aggregate report details will appear here.</p></div>}</div></div>}
    </>}
  </section>;
}

function CohortAssignmentPanel({ institutionId, canManage, canViewProgress }: { institutionId: number; canManage: boolean; canViewProgress: boolean }) {
  const [cohorts, setCohorts] = useState<Cohort[]>([]);
  const [cohortId, setCohortId] = useState<number | "">("");
  const scope = useRequestScope(`${institutionId}-${cohortId}`);
  const [detail, setDetail] = useState<{ cohortId: number; assignment: CohortAssignment; progress: CohortProgress | null } | null>(null);
  const assignment = detail?.cohortId === cohortId ? detail.assignment : null;
  const progress = detail?.cohortId === cohortId ? detail.progress : null;
  const [plans, setPlans] = useState<number[]>([]);
  const [activities, setActivities] = useState<number[]>([]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  const loadCohorts = useCallback(async () => {
    setLoading(true); setError("");
    try {
      const rows = await request<Cohort[]>(`/portal/${institutionId}/cohorts`);
      setCohorts(rows); setCohortId((current) => current || rows[0]?.id || "");
    } catch (reason) { setError(messageFor(reason)); }
    finally { setLoading(false); }
  }, [institutionId]);
  const loadDetail = useCallback(async () => {
    if (cohortId === "") return;
    setDetail(null);
    setBusy(false);
    setError(""); setNotice("");
    try {
      const [nextAssignment, nextProgress] = await Promise.all([
        request<CohortAssignment>(`/portal/${institutionId}/cohorts/${cohortId}/assignment`),
        canViewProgress ? request<CohortProgress>(`/portal/${institutionId}/cohorts/${cohortId}/progress`) : Promise.resolve(null),
      ]);
      if (!scope()) return;
      setDetail({ cohortId, assignment: nextAssignment, progress: nextProgress }); setPlans(nextAssignment.selected_plan_ids); setActivities(nextAssignment.selected_activity_ids);
    } catch (reason) { if (scope()) setError(messageFor(reason)); }
  }, [canViewProgress, cohortId, institutionId, scope]);
  useEffect(() => { const timer = window.setTimeout(() => void loadCohorts(), 0); return () => window.clearTimeout(timer); }, [loadCohorts]);
  useEffect(() => { const timer = window.setTimeout(() => void loadDetail(), 0); return () => window.clearTimeout(timer); }, [loadDetail]);
  const cohort = cohorts.find((item) => item.id === cohortId);
  const toggle = (items: number[], id: number) => items.includes(id) ? items.filter((item) => item !== id) : [...items, id];
  async function save() {
    if (cohortId === "") return;
    setBusy(true); setError(""); setNotice("");
    try {
      await request(`/portal/${institutionId}/cohorts/${cohortId}/assignment`, { method: "PUT", body: JSON.stringify({ selected_plan_ids: plans, selected_activity_ids: activities }) });
      if (!scope()) return;
      await loadDetail(); setNotice("Assignment updated.");
    }
    catch (reason) { if (scope()) setError(messageFor(reason)); }
    finally { if (scope()) setBusy(false); }
  }

  return <section className="assignment-panel" aria-label="Cohort assignment and progress"><div className="roster-heading"><div><p className="section-label">ASSIGNMENT / PROGRESS</p><h2>Cohort learning scope</h2><p className="page-subtitle">Validated activities and synthetic aggregate progress only. Raw media and advanced analytics are not implemented.</p></div></div>{error && <p className="alert alert--error" role="alert">{error}</p>}{notice && <p className="alert alert--success" role="status">{notice}</p>}{loading ? <div className="roster-empty" role="status">Loading assignment options…</div> : cohorts.length === 0 ? <div className="roster-empty"><strong>Create a cohort before assigning learning scope.</strong></div> : <><label className="form-field roster-select"><span className="field-label">Cohort</span><select value={cohortId} onChange={(event) => setCohortId(Number(event.target.value))}>{cohorts.map((item) => <option key={item.id} value={item.id}>{item.name} · {item.status}</option>)}</select></label>{assignment && <><div className="assignment-grid"><fieldset className="item-picker"><legend>Validated plans <span>({assignment.plans.length})</span></legend>{assignment.plans.length === 0 ? <p>No validated plans are available.</p> : assignment.plans.map((plan) => <label className="check-row" key={plan.id}><input type="checkbox" checked={plans.includes(plan.id)} onChange={() => setPlans(toggle(plans, plan.id))} disabled={!canManage || cohort?.status === "closed"} /><span><strong>{plan.code}</strong><small>{plan.label}</small></span></label>)}</fieldset><fieldset className="item-picker"><legend>Validated activities <span>({assignment.activities.length})</span></legend>{assignment.activities.length === 0 ? <p>No validated activities are available.</p> : assignment.activities.map((activity) => <label className="check-row" key={activity.id}><input type="checkbox" checked={activities.includes(activity.id)} onChange={() => setActivities(toggle(activities, activity.id))} disabled={!canManage || cohort?.status === "closed"} /><span><strong>{activity.prompt}</strong><small>{activity.plan_code} · activity #{activity.id}</small></span></label>)}</fieldset></div>{canManage && cohort?.status !== "closed" && <button className="button button--primary" onClick={() => void save()} disabled={busy}>{busy ? "Saving assignment…" : "Save assignment"}</button>}</>}{canViewProgress && progress && <ProgressView progress={progress} />}</>}</section>;
}

function ProgressView({ progress, onExport, exportBusy = false }: { progress: CohortProgress; onExport?: () => void; exportBusy?: boolean }) {
  const summary = progress.summary;
  const [localBusy, setLocalBusy] = useState(false);
  const [exportError, setExportError] = useState("");
  async function downloadReport() {
    setLocalBusy(true); setExportError("");
    try {
      const response = await fetch(`/api/portal/${progress.institution_id}/cohorts/${progress.cohort_id}/progress/export`, { credentials: "include" });
      if (!response.ok) throw new Error(`Export failed (${response.status})`);
      const url = URL.createObjectURL(await response.blob());
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = `cohort-${progress.cohort_id}-progress.csv`;
      document.body.appendChild(anchor);
      anchor.click();
      anchor.remove();
      URL.revokeObjectURL(url);
    } catch (reason) { setExportError(messageFor(reason)); }
    finally { setLocalBusy(false); }
  }
  const exportAction = onExport ?? (() => void downloadReport());
  const isExportBusy = onExport ? exportBusy : localBusy;
  return <div className="progress-view">
    <div className="progress-heading"><div><p className="section-label">SAFE PROGRESS REPORT</p><p className="quiet-copy">Controlled aggregate MVP report. Raw media and attempt payloads are excluded.</p></div><button className="button button--secondary" onClick={exportAction} disabled={isExportBusy}>{isExportBusy ? "Preparing report…" : "Export report"}</button></div>
    {exportError && <p className="alert alert--error" role="alert">{exportError}</p>}
    <div className="attribute-grid"><Attribute label="Enrolled (historical)" value={String(summary.enrolled_count)} /><Attribute label="Active now" value={String(summary.active_count)} /><Attribute label="Completed" value={`${summary.completed_count} / ${summary.active_count}`} /><Attribute label="Completion rate" value={`${Math.round(summary.completion_rate * 100)}%`} /><Attribute label="Attempts" value={String(summary.attempts.total)} /><Attribute label="Latency p50 / p95" value={`${summary.latency_ms.p50 ?? "—"} / ${summary.latency_ms.p95 ?? "—"} ms`} /></div>
    {progress.participants.length === 0 ? <p className="quiet-copy">No enrolled participants yet.</p> : <div className="progress-table"><table aria-label="Safe participant progress">
      <thead><tr>{["Participant", "Status", "Completion", "Attempts", "Correct / incorrect / unknown"].map((label) => <th scope="col" key={label}>{label}</th>)}</tr></thead>
      <tbody>{progress.participants.map((participant) => <tr key={participant.user_id}><th scope="row">{participant.identifier}</th><td>{participant.enrollment_status}</td><td>{participant.completed ? "Complete" : "In progress"}</td><td>{participant.attempts}</td><td>{participant.correct} / {participant.incorrect} / {participant.unknown}</td></tr>)}</tbody>
    </table></div>}
  </div>;
}

function parseIds(value: string) {
  return value.split(",").map((item) => Number(item.trim())).filter((item) => Number.isInteger(item) && item > 0);
}

function ParticipantRoster({ institutionId, canManage }: { institutionId: number; canManage: boolean }) {
  const [cohorts, setCohorts] = useState<Cohort[]>([]);
  const [members, setMembers] = useState<PortalMember[]>([]);
  const [roster, setRoster] = useState<{ cohortId: number; rows: PortalParticipant[] } | null>(null);
  const [cohortId, setCohortId] = useState<number | "">("");
  const scope = useRequestScope(`${institutionId}-${cohortId}`);
  const participants = roster?.cohortId === cohortId ? roster.rows : [];
  const [memberId, setMemberId] = useState<number | "">("");
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  const load = useCallback(async () => {
    if (!canManage) return;
    setLoading(true);
    setError("");
    try {
      const [cohortRows, memberRows] = await Promise.all([
        request<Cohort[]>(`/portal/${institutionId}/cohorts`),
        request<PortalMember[]>(`/portal/${institutionId}/members`),
      ]);
      setCohorts(cohortRows);
      setMembers(memberRows);
      setCohortId((current) => current || cohortRows[0]?.id || "");
    } catch (reason) {
      setError(messageFor(reason));
    } finally {
      setLoading(false);
    }
  }, [canManage, institutionId]);

  const loadParticipants = useCallback(async () => {
    if (cohortId === "") return;
    setMemberId(""); setError(""); setNotice(""); setBusy(false);
    try {
      const rows = await request<PortalParticipant[]>(`/portal/${institutionId}/cohorts/${cohortId}/participants`);
      if (scope()) setRoster({ cohortId, rows });
    } catch (reason) {
      if (scope()) setError(messageFor(reason));
    }
  }, [cohortId, institutionId, scope]);

  useEffect(() => {
    const timer = window.setTimeout(() => void load(), 0);
    return () => window.clearTimeout(timer);
  }, [load]);
  useEffect(() => {
    const timer = window.setTimeout(() => void loadParticipants(), 0);
    return () => window.clearTimeout(timer);
  }, [loadParticipants]);

  const selectedCohort = cohorts.find((cohort) => cohort.id === cohortId);
  const enrolledIds = new Set(participants.filter((participant) => participant.enrollment_status === "active").map((participant) => participant.user_id));
  const availableMembers = members.filter((member) => !enrolledIds.has(member.user_id));

  async function enroll(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (cohortId === "" || memberId === "" || roster?.cohortId !== cohortId) return;
    setBusy(true); setError(""); setNotice("");
    try {
      await request(`/portal/${institutionId}/cohorts/${cohortId}/participants`, { method: "POST", body: JSON.stringify({ user_id: memberId }) });
      if (!scope()) return;
      setMemberId(""); await loadParticipants(); setNotice("Participant enrolled.");
    } catch (reason) { if (scope()) setError(messageFor(reason)); } finally { if (scope()) setBusy(false); }
  }

  async function deactivate(userId: number) {
    if (cohortId === "" || !window.confirm("Deactivate this participant from the cohort? Their audit history will be preserved.")) return;
    setBusy(true); setError(""); setNotice("");
    try {
      await request(`/portal/${institutionId}/cohorts/${cohortId}/participants/${userId}/deactivate`, { method: "POST" });
      if (!scope()) return;
      await loadParticipants(); setNotice("Participant marked inactive.");
    } catch (reason) { if (scope()) setError(messageFor(reason)); } finally { if (scope()) setBusy(false); }
  }

  if (!canManage) return null;
  return <section className="roster-panel" aria-label="Participant roster">
    <div className="roster-heading"><div><p className="section-label">ENROLLMENT OVERSIGHT</p><h2>Participant roster</h2><p className="page-subtitle">Manage active institution members without exposing practice attempts or raw learner data.</p></div><span className="roster-count">{participants.filter((participant) => participant.enrollment_status === "active").length} active</span></div>
    {error && <p className="alert alert--error" role="alert">{error}</p>}
    {notice && <p className="alert alert--success" role="status">{notice}</p>}
    {loading ? <div className="roster-empty" role="status">Loading roster…</div> : cohorts.length === 0 ? <div className="roster-empty"><strong>Create a cohort before enrolling participants.</strong></div> : <>
      <label className="form-field roster-select"><span className="field-label">Cohort</span><select value={cohortId} onChange={(event) => setCohortId(Number(event.target.value))}>{cohorts.map((cohort) => <option key={cohort.id} value={cohort.id}>{cohort.name} · {cohort.status}</option>)}</select></label>
      {selectedCohort?.status !== "closed" && <form className="roster-enroll" onSubmit={enroll}><label className="form-field"><span className="field-label">Enroll an active member</span><select value={memberId} onChange={(event) => setMemberId(event.target.value ? Number(event.target.value) : "")}><option value="">Select a member</option>{availableMembers.map((member) => <option key={member.user_id} value={member.user_id}>{member.identifier}</option>)}</select></label><button className="button button--primary" disabled={busy || memberId === ""}>{busy ? "Working…" : "Enroll"}</button></form>}
      {participants.length === 0 ? <div className="roster-empty"><strong>No participants enrolled</strong><p>Only active members of this institution appear in the enrollment list.</p></div> : <div className="roster-list">{participants.map((participant) => <div className="roster-row" key={participant.participant_id}><span><strong>{participant.identifier}</strong><small>{participant.enrollment_status} · enrolled {new Date(participant.enrolled_at).toLocaleDateString()} · consent {participant.consent_status === "granted" ? "granted" : "not granted"}</small></span>{participant.enrollment_status === "active" && selectedCohort?.status !== "closed" && <button className="text-action text-action--danger" onClick={() => void deactivate(participant.user_id)} disabled={busy}>Deactivate</button>}</div>)}</div>}
    </>}
  </section>;
}

function CohortBadge({ status }: { status: CohortStatus }) {
  return <span className={`status-badge status-badge--${status}`}><i aria-hidden="true" />{status[0].toUpperCase() + status.slice(1)}</span>;
}

function CohortForm({ selected, onSubmit, onCancel, busy }: { selected: CohortDetail | null; onSubmit: (event: FormEvent<HTMLFormElement>) => void; onCancel: () => void; busy: boolean }) {
  return <div className="editor-panel"><div className="detail-topline"><p className="kicker">{selected ? "EDIT COHORT" : "NEW COHORT"}</p><button className="icon-button" type="button" onClick={onCancel} aria-label="Close editor">×</button></div><h2>{selected ? "Edit pilot cohort" : "Create pilot cohort"}</h2><p className="detail-intro">Use IDs from this institution&apos;s validated vocabulary. Flutter will consume planned and active cohorts.</p><form className="form-stack record-form" onSubmit={onSubmit}><Field label="Cohort name" name="name" required defaultValue={selected?.name} /><Field label="Start date" name="start_date" type="date" required defaultValue={selected?.start_date} /><Field label="End date" name="end_date" type="date" defaultValue={selected?.end_date ?? ""} />{selected && <label className="form-field"><span className="field-label">Status</span><select name="status" defaultValue={selected.status}><option value="planned">Planned</option><option value="active">Active</option><option value="closed">Closed</option></select></label>}<label className="check-row"><input type="checkbox" name="consent_required" defaultChecked={selected?.consent_required ?? true} /><span><strong>Require practice consent</strong><small>Keep participant consent explicit for practice attempts.</small></span></label><Field label="Validated plan IDs" name="selected_plan_ids" defaultValue={selected?.selected_plan_ids.join(", ")} /><Field label="Validated activity IDs" name="selected_activity_ids" defaultValue={selected?.selected_activity_ids.join(", ")} /><div className="form-actions"><button type="button" className="button button--quiet" onClick={onCancel} disabled={busy}>Cancel</button><button className="button button--primary" disabled={busy}>{busy ? "Saving…" : selected ? "Save changes" : "Create cohort"}</button></div></form></div>;
}

function Field({ label, name, type = "text", required = false, defaultValue, autoComplete }: {
  label: string; name: string; type?: string; required?: boolean; defaultValue?: string | number; autoComplete?: string;
}) {
  return <label className="form-field"><span className="field-label">{label}{required && <span aria-hidden="true"> *</span>}</span><input name={name} type={type} required={required} defaultValue={defaultValue} autoComplete={autoComplete} /></label>;
}

function RecordForm({ institutionId, section, selected, concepts, signs, variants: suppliedVariants, onConcept, onSign, onPlan, onCancel, busy }: {
  institutionId: number;
  section: Section; selected: Concept | Sign | Plan | null; concepts: Concept[]; signs: Sign[]; variants: Variant[];
  onConcept: (event: FormEvent<HTMLFormElement>) => void; onSign: (event: FormEvent<HTMLFormElement>) => void;
  onPlan: (event: FormEvent<HTMLFormElement>) => void; onCancel: () => void; busy: boolean;
}) {
  const [planVariants, setPlanVariants] = useState<Variant[] | null>(null);
  const [variantError, setVariantError] = useState("");
  const [variantAttempt, setVariantAttempt] = useState(0);
  useEffect(() => {
    if (section !== "plans") return;
    let active = true;
    Promise.all(signs.map((sign) => request<Variant[]>(`/vocabulary/${institutionId}/signs/${sign.id}/variants`)))
      .then((rows) => { if (active) { setPlanVariants(rows.flat()); setVariantError(""); } })
      .catch((reason) => { if (active) setVariantError(messageFor(reason)); });
    return () => { active = false; };
  }, [institutionId, section, signs, variantAttempt]);
  const variants = section === "plans" ? planVariants ?? [] : suppliedVariants;
  const editing = Boolean(selected);
  const title = section === "concepts" ? "Concept" : section === "signs" ? "Sign" : "Sign plan";
  return (
    <div className="editor-panel">
      <div className="detail-topline"><p className="kicker">{editing ? "EDIT RECORD" : "NEW RECORD"}</p><button className="icon-button" type="button" onClick={onCancel} aria-label="Close editor">×</button></div>
      <h2>{editing ? `Edit ${title.toLowerCase()}` : `Create ${title.toLowerCase()}`}</h2>
      <p className="detail-intro">{section === "concepts" ? "Give this concept a stable institutional code and a clear label." : section === "signs" ? "Connect a sign identifier and gloss to an existing concept." : "Compose a sequence using signs already registered for this institution."}</p>
      {section === "plans" && planVariants === null && <p role="status">Loading sign variants…</p>}
      {variantError && <div role="alert"><p>{variantError}</p><button type="button" className="button button--secondary" onClick={() => setVariantAttempt((value) => value + 1)}>Retry variants</button></div>}
      <form className="form-stack record-form" onSubmit={section === "concepts" ? onConcept : section === "signs" ? onSign : onPlan}>
        {section === "concepts" ? <>
          <Field label="Concept code" name="code" required={!editing} defaultValue={(selected as Concept | null)?.code} />
          <Field label="Label" name="label" required defaultValue={(selected as Concept | null)?.label} />
          <label className="form-field"><span className="field-label">Description</span><textarea name="description" rows={4} defaultValue={(selected as Concept | null)?.description} /></label>
        </> : section === "signs" ? <>
          {!editing && <Field label="Stable sign identifier" name="sign_id" required />}
          <label className="form-field"><span className="field-label">Concept *</span><select name="concept_id" required defaultValue={(selected as Sign | null)?.concept_id ?? ""}><option value="" disabled>Select a concept</option>{concepts.map((concept) => <option key={concept.id} value={concept.id}>{concept.label} · {concept.code}</option>)}</select></label>
          <Field label="Gloss" name="gloss" required defaultValue={(selected as Sign | null)?.gloss} />
          <Field label="Language" name="language" required defaultValue={(selected as Sign | null)?.language ?? "lsb"} />
        </> : <>
          {!editing && <Field label="Plan code" name="code" required />}
          <label className="form-field"><span className="field-label">Concept *</span><select name="concept_id" required defaultValue={(selected as Plan | null)?.concept_id ?? ""}><option value="" disabled>Select a concept</option>{concepts.map((concept) => <option key={concept.id} value={concept.id}>{concept.label} · {concept.code}</option>)}</select></label>
          <Field label="Language" name="language" required defaultValue={(selected as Plan | null)?.language ?? "lsb"} />
          <Field label="Plan variant" name="variant" defaultValue={(selected as Plan | null)?.variant} />
          <fieldset className="item-picker"><legend>Ordered signs <span>({signs.length} available)</span></legend>{signs.length === 0 ? <p>Add signs before composing a plan.</p> : <div className="item-picker__list">{signs.map((sign, index) => {
            const existingItem = (selected as Plan | null)?.items.find((item) => item.sign_id === sign.id);
            const signVariants = variants.filter((variant) => variant.sign_id === sign.id);
            return <div key={sign.id} className="plan-sign-row"><label className="check-row"><input type="checkbox" name="items" value={sign.id} defaultChecked={Boolean(existingItem)} /><span><strong>{sign.gloss}</strong><small>{sign.sign_id} · database record {sign.id}</small></span>{sign.status !== "validated" && <em>Not validated</em>}</label><label className="order-field"><span className="sr-only">Order for {sign.gloss}</span><input type="number" name={`position-${sign.id}`} min="1" defaultValue={existingItem ? existingItem.position + 1 : index + 1} /></label>{signVariants.length > 0 && <label className="variant-select"><span className="sr-only">Variant for {sign.gloss}</span><select name={`variant-${sign.id}`} defaultValue={existingItem?.variant_id ?? ""}><option value="">No variant</option>{signVariants.map((variant) => <option key={variant.id} value={variant.id}>{variant.label || variant.variant_code}</option>)}</select></label>}</div>;
          })}</div>}</fieldset>
          <label className="form-field"><span className="field-label">Non-manual markers <span className="field-hint">JSON array, positions start at 0</span></span><textarea name="markers" rows={5} defaultValue={JSON.stringify((selected as Plan | null)?.non_manual_markers ?? [], null, 2)} spellCheck={false} /></label>
        </>}
        <div className="form-actions"><button type="button" className="button button--quiet" onClick={onCancel} disabled={busy}>Cancel</button><button className="button button--primary" disabled={busy || (section === "plans" && planVariants === null)}>{busy ? "Saving…" : editing ? "Save changes" : `Create ${title.toLowerCase()}`}</button></div>
      </form>
    </div>
  );
}

function DetailHeader({ eyebrow, title, code, status }: { eyebrow: string; title: string; code: string; status?: Status }) {
  return <><div className="detail-topline"><p className="kicker">{eyebrow}</p>{status && <StatusBadge status={status} />}</div><h2 className="detail-title">{title}</h2><p className="record-code">{code}</p></>;
}

function ConceptDetail({ concept, aliases, onEdit, onDelete, onAddAlias, onEditAlias, onDeleteAlias, busy }: {
  concept: Concept; aliases: Alias[]; onEdit: () => void; onDelete: () => void;
  onAddAlias: (event: FormEvent<HTMLFormElement>) => void; onEditAlias: (alias: Alias) => void;
  onDeleteAlias: (alias: Alias) => void; busy: boolean;
}) {
  return <div className="detail-content"><DetailHeader eyebrow="CONCEPT / VOCABULARY ROOT" title={concept.label} code={concept.code} />
    <div className="detail-actions"><button className="button button--secondary" onClick={onEdit} disabled={busy}>Edit concept</button><button className="button button--danger-quiet" onClick={onDelete} disabled={busy}>Delete</button></div>
    <div className="detail-section"><p className="section-label">DESCRIPTION</p><p className="description-copy">{concept.description || "No description has been added."}</p></div>
    <div className="detail-section"><div className="section-heading"><div><p className="section-label">ALTERNATE TERMS</p><h3>Aliases <span className="count-pill">{aliases.length}</span></h3></div></div>
      {aliases.length ? <ul className="alias-list">{aliases.map((alias) => <li key={alias.id}><span>{alias.alias}</span><span className="inline-actions"><button className="text-action" onClick={() => onEditAlias(alias)} disabled={busy}>Edit</button><button className="text-action text-action--danger" onClick={() => onDeleteAlias(alias)} disabled={busy}>Remove</button></span></li>)}</ul> : <p className="quiet-copy">No aliases recorded for this concept.</p>}
      <form className="inline-form" onSubmit={onAddAlias}><label className="sr-only" htmlFor="new-alias">New alias</label><input id="new-alias" name="alias" placeholder="Add an alternate term" required maxLength={200} /><button className="button button--secondary" disabled={busy}>Add alias</button></form>
    </div>
  </div>;
}

function SignDetail({ sign, concept, variants, canDeleteVariant, onEdit, onDelete, onTransition, onAddVariant, onEditVariant, onDeleteVariant, busy }: {
  sign: Sign; concept?: Concept; variants: Variant[]; canDeleteVariant: (variant: Variant) => boolean; onEdit: () => void; onDelete: () => void;
  onTransition: (action: "review" | "validate" | "reject" | "reopen") => void;
  onAddVariant: (event: FormEvent<HTMLFormElement>) => void; onEditVariant: (variant: Variant) => void; onDeleteVariant: (variant: Variant) => void; busy: boolean;
}) {
  return <div className="detail-content"><DetailHeader eyebrow="SIGN / LEXICAL RECORD" title={sign.gloss} code={sign.sign_id} status={sign.status} />
    <div className="detail-actions"><button className="button button--secondary" onClick={onEdit} disabled={busy || !["draft", "rejected"].includes(sign.status)}>Edit sign</button><button className="button button--danger-quiet" onClick={onDelete} disabled={busy || sign.status === "validated"}>Delete</button></div>
    <div className="attribute-grid"><Attribute label="Concept" value={concept ? `${concept.label} · ${concept.code}` : `Concept ${sign.concept_id}`} /><Attribute label="Language" value={sign.language.toUpperCase()} /><Attribute label="Record ID" value={`#${sign.id}`} /></div>
    <Lifecycle status={sign.status} kind="sign" onAction={onTransition} busy={busy} />
    <div className="detail-section"><div className="section-heading"><div><p className="section-label">SIGN FORMS</p><h3>Variants <span className="count-pill">{variants.length}{variants.length === 0 ? "+" : ""}</span></h3></div></div>
      {variants.length ? <ul className="variant-list">{variants.map((variant) => <li key={variant.id}><div><strong>{variant.label || variant.variant_code}</strong><span>{variant.variant_code} · record #{variant.id}</span>{variant.hamnosys && <code>{variant.hamnosys}</code>}<button className="text-action" onClick={() => onEditVariant(variant)} disabled={busy}>Edit label</button>{canDeleteVariant(variant) && <button className="text-action text-action--danger" onClick={() => onDeleteVariant(variant)} disabled={busy}>Delete</button>}</div></li>)}</ul> : <p className="quiet-copy">No variants are recorded for this sign.</p>}
      <form className="form-stack variant-form" onSubmit={onAddVariant}><p className="section-label">ADD A VARIANT</p><Field label="Variant code" name="variant_code" required /><Field label="Label" name="label" /><label className="form-field"><span className="field-label">HamNoSys notation <span className="field-hint">Optional opaque notation</span></span><textarea name="hamnosys" rows={2} /></label><button className="button button--secondary" disabled={busy}>Add variant</button></form>
    </div>
  </div>;
}

function PlanDetail({ plan, concept, onEdit, onDelete, onTransition, busy }: {
  plan: Plan; concept?: Concept; onEdit: () => void; onDelete: () => void;
  onTransition: (action: "review" | "validate" | "reject" | "reopen") => void; busy: boolean;
}) {
  return <div className="detail-content"><DetailHeader eyebrow="SIGN PLAN / SEQUENCE" title={plan.code} code={`${plan.language.toUpperCase()}${plan.variant ? ` · ${plan.variant}` : ""}`} status={plan.status} />
    <div className="detail-actions"><button className="button button--secondary" onClick={onEdit} disabled={busy || !["draft", "rejected"].includes(plan.status)}>Edit plan</button><button className="button button--danger-quiet" onClick={onDelete} disabled={busy || plan.status === "validated"}>Delete</button></div>
    <div className="attribute-grid"><Attribute label="Concept" value={concept ? `${concept.label} · ${concept.code}` : `Concept ${plan.concept_id}`} /><Attribute label="Ordered signs" value={`${plan.items.length} ${plan.items.length === 1 ? "sign" : "signs"}`} /></div>
    <Lifecycle status={plan.status} kind="plan" onAction={onTransition} busy={busy} />
    <div className="detail-section"><p className="section-label">SEQUENCE / IN ORDER</p>{plan.items.length ? <ol className="sequence-list">{plan.items.map((item) => <li key={`${item.position}-${item.sign_id}`}><span className="sequence-index">{String(item.position + 1).padStart(2, "0")}</span><span className="sequence-word"><strong>{item.gloss}</strong><small>{item.stable_sign_id}</small></span><span className="sequence-pk">PK {item.sign_id}</span></li>)}</ol> : <p className="quiet-copy">This plan has no signs yet.</p>}</div>
    <div className="detail-section"><p className="section-label">NON-MANUAL MARKERS</p>{plan.non_manual_markers.length ? <ul className="marker-list">{plan.non_manual_markers.map((marker, index) => <li key={`${marker.kind}-${index}`}><strong>{marker.kind}</strong><span>{marker.value}</span><small>Items {marker.start_position + 1}–{marker.end_position + 1}</small></li>)}</ul> : <p className="quiet-copy">No non-manual markers recorded.</p>}</div>
  </div>;
}

function Attribute({ label, value }: { label: string; value: string }) {
  return <div className="attribute"><span>{label}</span><strong>{value}</strong></div>;
}

function Lifecycle({ status, kind, onAction, busy }: {
  status: Status; kind: "sign" | "plan";
  onAction: (action: "review" | "validate" | "reject" | "reopen") => void; busy: boolean;
}) {
  const actions: { action: "review" | "validate" | "reject" | "reopen"; label: string; style: string }[] = status === "draft"
    ? [{ action: "review", label: "Submit for review", style: "primary" }]
    : status === "in_review"
      ? [{ action: "validate", label: "Validate", style: "primary" }, { action: "reject", label: "Reject", style: "danger" }]
      : status === "rejected"
        ? [{ action: "reopen", label: "Reopen as draft", style: "secondary" }]
        : [];
  return <section className="lifecycle" aria-label={`${kind} review lifecycle`}><div className="lifecycle__copy"><p className="section-label">REVIEW PATH</p><div className="lifecycle-track">{(["draft", "in_review", "validated"] as Status[]).map((step, index) => <span key={step} className={`lifecycle-step ${status === step ? "is-current" : ""} ${status === "rejected" && index === 1 ? "is-rejected" : ""}`}><i aria-hidden="true" />{statusLabel(step)}{index < 2 && <b aria-hidden="true" />}</span>)}</div>{status === "rejected" && <p className="rejected-note">Rejected records can be edited and reopened as drafts.</p>}</div><div className="lifecycle__actions">{actions.map((item) => <button key={item.action} className={`button button--${item.style}`} onClick={() => onAction(item.action)} disabled={busy}>{item.label}</button>)}</div></section>;
}

function StatusBadge({ status }: { status: Status }) {
  return <span className={`status-badge status-badge--${status}`}><i aria-hidden="true" />{statusLabel(status)}</span>;
}
