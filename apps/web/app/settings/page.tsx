"use client";

import { FormEvent, useEffect, useState } from "react";
import type { components } from "../../../../contracts/generated/api-types";
import { PageHeader, StatusMessage } from "../components/app-shell";
import {
  apiLoginUrl,
  apiMfaSetupUrl,
  apiRequest,
  displayError,
} from "../lib/api";

type Schedule = components["schemas"]["ScheduleRead"];
type Preference = components["schemas"]["PreferenceRead"];
type Activity = components["schemas"]["ActivityRead"];

interface MfaSetup {
  secret_code: string;
  account_name: string;
  issuer: string;
}

export default function SettingsPage() {
  const [schedule, setSchedule] = useState<Schedule | null>(null);
  const [preference, setPreference] = useState<Preference | null>(null);
  const [activity, setActivity] = useState<Activity[]>([]);
  const [mfaSetup, setMfaSetup] = useState<MfaSetup | null>(null);
  const [message, setMessage] = useState("");

  useEffect(() => {
    void Promise.all([
      apiRequest<Schedule>("/settings/schedule").catch(() => null),
      apiRequest<Preference>("/notifications/preference").catch(() => null),
      apiRequest<Activity[]>("/account/activity").catch(() => []),
    ]).then(([nextSchedule, nextPreference, nextActivity]) => {
      setSchedule(nextSchedule);
      setPreference(nextPreference);
      setActivity(nextActivity);
    });
    if (new URLSearchParams(window.location.search).get("mfa") === "setup") {
      void apiRequest<MfaSetup>("/auth/mfa/setup-details")
        .then(setMfaSetup)
        .catch((error: unknown) => setMessage(displayError(error)));
    }
  }, []);

  async function saveSchedule(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    try {
      const result = await apiRequest<Schedule>("/settings/schedule", {
        method: "PUT",
        body: JSON.stringify({
          timezone: data.get("timezone"),
          local_time: data.get("local_time"),
          enabled: data.get("enabled") === "on",
        }),
      });
      setSchedule(result);
      setMessage("Daily schedule saved.");
    } catch (error) {
      setMessage(displayError(error));
    }
  }

  async function savePreference(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    const channel = String(data.get("channel"));
    try {
      const result = await apiRequest<Preference>("/notifications/preference", {
        method: "PUT",
        body: JSON.stringify({
          external_channel: channel,
          enabled: channel !== "NONE",
          destination: data.get("destination") || null,
        }),
      });
      setPreference(result);
      setMessage("Notification preference saved. DireHire will not fail over to another channel.");
    } catch (error) {
      setMessage(displayError(error));
    }
  }

  async function verifyMfa(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    try {
      await apiRequest<void>("/auth/mfa/verify", {
        method: "POST",
        body: JSON.stringify({ code: data.get("code") }),
      });
      window.location.replace(apiLoginUrl());
    } catch (error) {
      setMessage(displayError(error));
    }
  }

  return (
    <>
      <PageHeader eyebrow="Account defaults" title="Settings" />
      <StatusMessage>{message}</StatusMessage>
      <div className="split-layout">
        <section className="surface">
          <h2>Account security</h2>
          <p className="supporting">
            An authenticator is optional for normal accounts and required for operational roles.
          </p>
          {mfaSetup ? (
            <form onSubmit={verifyMfa}>
              <p className="hint">
                In your authenticator app, add a time-based account for <strong>{mfaSetup.account_name}</strong>
                {" "}under <strong>{mfaSetup.issuer}</strong> using this setup key:
              </p>
              <code className="setup-secret">{mfaSetup.secret_code}</code>
              <label>
                Six-digit code
                <input name="code" inputMode="numeric" pattern="[0-9]{6}" autoComplete="one-time-code" required />
              </label>
              <button className="button primary">Verify and enable</button>
            </form>
          ) : (
            <a className="button" href={apiMfaSetupUrl()}>Enable authenticator</a>
          )}
        </section>
        <section className="surface">
          <h2>Daily Watch schedule</h2>
          <form onSubmit={saveSchedule}>
            <label>Timezone<input name="timezone" required defaultValue={schedule?.timezone ?? Intl.DateTimeFormat().resolvedOptions().timeZone} /></label>
            <label>Local run time<input name="local_time" type="time" required defaultValue={schedule?.local_time?.slice(0, 5) ?? "08:00"} /></label>
            <label className="check"><input name="enabled" type="checkbox" defaultChecked={schedule?.enabled ?? true} /> Run active Watches daily</label>
            <button className="button primary">Save schedule</button>
          </form>
          {schedule?.next_run_at && <p className="hint">Next run: {new Date(schedule.next_run_at).toLocaleString()}</p>}
        </section>
      </div>
      <section className="surface">
        <h2>Optional digest channel</h2>
        <p className="supporting">In-app notifications remain the source of truth. Choose at most one external channel.</p>
        <form onSubmit={savePreference}>
          <label>Channel<select name="channel" defaultValue={preference?.external_channel ?? "NONE"}><option value="NONE">In-app only</option><option value="TELEGRAM">Telegram</option><option value="WHATSAPP">WhatsApp</option></select></label>
          <label>Destination<input name="destination" placeholder={preference?.destination_hint ?? "Chat ID or phone number"} /></label>
          <button className="button primary">Save preference</button>
        </form>
      </section>
      <section className="surface">
        <h2>Account activity</h2>
        <ul className="plain-list">{activity.map((item) => <li key={item.id}><span>{item.activity_type.replaceAll("_", " ")}</span><time dateTime={item.created_at}>{new Date(item.created_at).toLocaleString()}</time></li>)}</ul>
      </section>
    </>
  );
}
