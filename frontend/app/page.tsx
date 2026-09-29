import Link from "next/link";

export default function Home() {
  const apiBaseUrl = process.env.NEXT_PUBLIC_API_BASE_URL ?? "/api";

  return (
    <div className="admin-shell">
      <header className="topbar">
        <Link className="brand" href="/" aria-label="DualSign administration home">
          <span className="brand__mark" aria-hidden="true">
            DS
          </span>
          <span className="brand__text">
            <strong>DualSign</strong>
            <span>ADMINISTRATION</span>
          </span>
        </Link>
        <div className="environment-label">
          <span className="environment-label__dot" aria-hidden="true" />
          Local development
        </div>
      </header>

      <main className="workspace">
        <section className="intro" aria-labelledby="page-title">
          <p className="eyebrow">PHASE 0 / FOUNDATION</p>
          <h1 id="page-title">Administrative workspace</h1>
          <p className="intro__summary">
            A starting point for platform operations. Product workflows are not
            part of this phase.
          </p>
        </section>

        <section className="api-panel" aria-labelledby="api-title">
          <div className="api-panel__copy">
            <p className="eyebrow">API BOUNDARY</p>
            <h2 id="api-title">Check the service endpoint</h2>
            <p>
              Requests use the same origin as this page and are routed through
              Nginx to the Django API.
            </p>
            <a
              className="api-link"
              href={`${apiBaseUrl.replace(/\/$/, "")}/health`}
            >
              Open health response <span aria-hidden="true">↗</span>
            </a>
          </div>
          <div className="route-card" aria-label="Health request path">
            <span>REQUEST PATH</span>
            <code>{`${apiBaseUrl.replace(/\/$/, "")}/health`}</code>
          </div>
        </section>

        <footer className="workspace-footer">
          Phase 0 local development <span aria-hidden="true">·</span> No product
          data is available
        </footer>
      </main>
    </div>
  );
}
