import Link from "next/link";

export default function Home() {
  return (
    <main className="product-home">
      <p className="kicker">DUALSIGN PRODUCT SURFACES</p>
      <h1>One language platform.<br />Clear boundaries.</h1>
      <p className="subtle">DualSign separates internal operations from company workspaces while the mobile app serves end users.</p>
      <div className="surface-grid">
        <Link className="surface-card" href="/portal"><span className="kicker">COMPANY SAAS</span><strong>Open the portal</strong><span>Institution-scoped vocabulary workspace for active members.</span></Link>
        <Link className="surface-card" href="/backoffice"><span className="kicker">INTERNAL DUALSIGN</span><strong>Open backoffice</strong><span>Operations shell for platform staff. Enterprise controls are not live yet.</span></Link>
      </div>
      <p className="home-note">Flutter is the consumer/mobile surface. Free, Plus, and enterprise access are represented as entitlements; billing and Stripe are future work.</p>
    </main>
  );
}
