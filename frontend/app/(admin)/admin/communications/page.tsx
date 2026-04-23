import { CommunicationsPanel } from "./communications-panel";

export const dynamic = "force-dynamic";

export default function CommunicationsPage() {
  return (
    <section aria-labelledby="comms-heading">
      <h1 id="comms-heading" className="text-2xl font-bold text-dark">
        Communications
      </h1>
      <p className="mt-1 text-sm text-dark/70">
        Manage notification templates and fire off batch email or SMS to
        filtered cohorts. Every batch lands in the audit log with a hash of
        the rendered content.
      </p>
      <div className="mt-6">
        <CommunicationsPanel />
      </div>
    </section>
  );
}
