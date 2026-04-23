import { ProfileForm } from "./profile-form";

export const dynamic = "force-dynamic";

export default function ProfilePage() {
  return (
    <section aria-labelledby="profile-heading">
      <h1 id="profile-heading" className="text-2xl font-bold text-dark">
        My Profile
      </h1>
      <p className="mt-1 text-sm text-dark/70">
        Keep your contact details current — we use these to send payment reminders,
        registration confirmations, and important programme notices.
      </p>
      <div className="mt-6">
        <ProfileForm />
      </div>
    </section>
  );
}
