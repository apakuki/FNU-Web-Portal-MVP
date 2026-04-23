"use client";

import { useEffect, useRef, useState } from "react";

import { apiFetch, ApiError } from "@/lib/api-client";

type Profile = {
  user_id: string;
  full_name: string;
  email: string;
  phone: string | null;
  banner_id: string | null;
  address_line1: string | null;
  address_line2: string | null;
  city: string | null;
  country: string | null;
  emergency_contact_name: string | null;
  emergency_contact_phone: string | null;
  emergency_contact_relationship: string | null;
  has_photo: boolean;
};

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "";

export function ProfileForm() {
  const [profile, setProfile] = useState<Profile | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [photoVersion, setPhotoVersion] = useState(0);
  const fileInputRef = useRef<HTMLInputElement | null>(null);

  useEffect(() => {
    apiFetch<Profile>("/api/profile")
      .then(setProfile)
      .catch((e: Error) => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  async function handleSave(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    if (!profile) return;
    setSaving(true);
    setError(null);
    setSuccess(null);

    const formData = new FormData(e.currentTarget);
    const payload = {
      phone: (formData.get("phone") as string) || null,
      email: (formData.get("email") as string) || null,
      address_line1: (formData.get("address_line1") as string) || null,
      address_line2: (formData.get("address_line2") as string) || null,
      city: (formData.get("city") as string) || null,
      country: (formData.get("country") as string) || null,
      emergency_contact_name:
        (formData.get("emergency_contact_name") as string) || null,
      emergency_contact_phone:
        (formData.get("emergency_contact_phone") as string) || null,
      emergency_contact_relationship:
        (formData.get("emergency_contact_relationship") as string) || null,
    };

    try {
      const updated = await apiFetch<Profile>("/api/profile", {
        method: "PUT",
        body: JSON.stringify(payload),
      });
      setProfile(updated);
      setSuccess("Profile saved");
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Failed to save profile");
    } finally {
      setSaving(false);
    }
  }

  async function handlePhoto(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    if (file.size > 2 * 1024 * 1024) {
      setError("Photo must be 2MB or less");
      return;
    }
    setSaving(true);
    setError(null);

    const fd = new FormData();
    fd.append("file", file);

    const { getSession } = await import("next-auth/react");
    const session = await getSession();
    const token = (session?.user as { accessToken?: string } | null | undefined)
      ?.accessToken;

    try {
      const res = await fetch(`${API_BASE}/api/profile/photo`, {
        method: "POST",
        body: fd,
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      });
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        throw new Error(body.detail ?? "Upload failed");
      }
      const updated = (await res.json()) as Profile;
      setProfile(updated);
      setPhotoVersion((v) => v + 1);
      setSuccess("Photo updated");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Upload failed");
    } finally {
      setSaving(false);
      if (fileInputRef.current) fileInputRef.current.value = "";
    }
  }

  if (loading) return <p className="text-sm text-dark/60">Loading profile…</p>;
  if (!profile)
    return (
      <p className="text-sm text-danger">{error ?? "Failed to load profile"}</p>
    );

  return (
    <form onSubmit={handleSave} className="space-y-6" aria-busy={saving}>
      <div className="rounded border bg-white p-4">
        <h2 className="text-lg font-semibold text-dark">Photo</h2>
        <div className="mt-3 flex items-center gap-4">
          <div
            className="h-24 w-24 overflow-hidden rounded-full bg-surface ring-1 ring-dark/10"
            aria-label="Profile photo"
          >
            {profile.has_photo ? (
              /* eslint-disable-next-line @next/next/no-img-element */
              <img
                src={`${API_BASE}/api/profile/photo/me?v=${photoVersion}`}
                alt="Profile"
                className="h-full w-full object-cover"
              />
            ) : (
              <div className="flex h-full w-full items-center justify-center text-xs text-dark/50">
                No photo
              </div>
            )}
          </div>
          <div>
            <input
              ref={fileInputRef}
              type="file"
              accept="image/jpeg,image/png,image/webp"
              onChange={handlePhoto}
              className="block text-sm"
              aria-label="Upload profile photo"
            />
            <p className="mt-1 text-xs text-dark/60">
              JPG, PNG, or WebP, up to 2MB. Resized to 400×400.
            </p>
          </div>
        </div>
      </div>

      <fieldset className="rounded border bg-white p-4">
        <legend className="px-1 text-lg font-semibold text-dark">Identity</legend>
        <div className="grid gap-4 sm:grid-cols-2">
          <Field label="Full name" value={profile.full_name} readOnly />
          <Field label="Banner ID" value={profile.banner_id ?? "—"} readOnly />
          <TextField
            label="Email"
            name="email"
            type="email"
            defaultValue={profile.email}
            required
          />
          <TextField
            label="Phone"
            name="phone"
            type="tel"
            defaultValue={profile.phone ?? ""}
            placeholder="+679 999 9999"
          />
        </div>
      </fieldset>

      <fieldset className="rounded border bg-white p-4">
        <legend className="px-1 text-lg font-semibold text-dark">Address</legend>
        <div className="grid gap-4 sm:grid-cols-2">
          <TextField
            label="Address line 1"
            name="address_line1"
            defaultValue={profile.address_line1 ?? ""}
            className="sm:col-span-2"
          />
          <TextField
            label="Address line 2"
            name="address_line2"
            defaultValue={profile.address_line2 ?? ""}
            className="sm:col-span-2"
          />
          <TextField label="City" name="city" defaultValue={profile.city ?? ""} />
          <TextField
            label="Country"
            name="country"
            defaultValue={profile.country ?? "Fiji"}
          />
        </div>
      </fieldset>

      <fieldset className="rounded border bg-white p-4">
        <legend className="px-1 text-lg font-semibold text-dark">
          Emergency contact
        </legend>
        <div className="grid gap-4 sm:grid-cols-2">
          <TextField
            label="Name"
            name="emergency_contact_name"
            defaultValue={profile.emergency_contact_name ?? ""}
          />
          <TextField
            label="Phone"
            name="emergency_contact_phone"
            defaultValue={profile.emergency_contact_phone ?? ""}
            placeholder="+679 999 9999"
          />
          <TextField
            label="Relationship"
            name="emergency_contact_relationship"
            defaultValue={profile.emergency_contact_relationship ?? ""}
          />
        </div>
      </fieldset>

      {error && (
        <p role="alert" className="rounded bg-danger/10 p-2 text-sm text-danger">
          {error}
        </p>
      )}
      {success && (
        <p role="status" className="rounded bg-success/10 p-2 text-sm text-success">
          {success}
        </p>
      )}

      <div className="flex justify-end">
        <button
          type="submit"
          disabled={saving}
          className="min-h-[44px] rounded bg-fnu-blue px-6 py-2 text-sm font-medium text-white transition hover:bg-fnu-blue/90 disabled:opacity-60"
        >
          {saving ? "Saving…" : "Save changes"}
        </button>
      </div>
    </form>
  );
}

function Field({
  label,
  value,
  readOnly,
}: {
  label: string;
  value: string;
  readOnly?: boolean;
}) {
  return (
    <label className="block text-sm">
      <span className="mb-1 block font-medium text-dark">{label}</span>
      <input
        type="text"
        value={value}
        readOnly={readOnly}
        className="w-full rounded border bg-surface/60 px-3 py-2 text-dark/80"
      />
    </label>
  );
}

function TextField({
  label,
  name,
  type = "text",
  defaultValue,
  placeholder,
  required,
  className,
}: {
  label: string;
  name: string;
  type?: string;
  defaultValue?: string;
  placeholder?: string;
  required?: boolean;
  className?: string;
}) {
  return (
    <label className={`block text-sm ${className ?? ""}`}>
      <span className="mb-1 block font-medium text-dark">{label}</span>
      <input
        type={type}
        name={name}
        defaultValue={defaultValue}
        placeholder={placeholder}
        required={required}
        className="w-full rounded border px-3 py-2 focus:border-fnu-blue focus:outline-none"
      />
    </label>
  );
}
