import { IdCardView } from "./id-card-view";

export const dynamic = "force-dynamic";

export default function IdCardPage() {
  return (
    <section aria-labelledby="id-card-heading">
      <h1 id="id-card-heading" className="text-2xl font-bold text-dark">
        Student ID Card
      </h1>
      <p className="mt-1 text-sm text-dark/70">
        Show this card at the library, labs, and exams. The QR code verifies
        your enrolment status in real time.
      </p>
      <div className="mt-6">
        <IdCardView />
      </div>
    </section>
  );
}
