"use client";

import { FormEvent, useCallback, useState } from "react";
import type { components } from "../../../../contracts/generated/api-types";

import { PageHeader, StatusMessage } from "../components/app-shell";
import { apiRequest, commaList, displayError } from "../lib/api";
import { useInitialLoad } from "../lib/use-initial-load";

type Watch = components["schemas"]["WatchRead"];

const adapters = [
  ["greenhouse", "Greenhouse"], ["lever", "Lever"], ["ashby", "Ashby"],
  ["recruitee", "Recruitee"], ["personio", "Personio"], ["pinpoint", "Pinpoint"],
  ["generic_public", "Other public careers page"],
];

export default function WatchesPage() {
  const [watches, setWatches] = useState<Watch[]>([]);
  const [message, setMessage] = useState("Loading Watches…");
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    try { setWatches(await apiRequest<Watch[]>("/watches")); setMessage(""); }
    catch (error) { setMessage(displayError(error)); }
  }, []);
  useInitialLoad(load);

  async function create(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    const data = new FormData(form);
    const sourceUrl = String(data.get("source_url") ?? "").trim();
    setBusy(true);
    try {
      const created = await apiRequest<Watch>("/watches", {
        method: "POST",
        body: JSON.stringify({
          name: data.get("name"), target_terms: commaList(data.get("targets")),
          required_terms: commaList(data.get("required")), excluded_terms: commaList(data.get("excluded")),
          locations: commaList(data.get("locations")), experience_target: data.get("experience") || null,
          posting_age_days: Number(data.get("age")),
          sources: sourceUrl ? [{ source_kind: "CUSTOM_URL", adapter_key: data.get("adapter"), url: sourceUrl }] : [],
        }),
      });
      setWatches((current) => [...current, created]);
      setMessage(`${created.name} was saved as a draft. Activate it when ready.`);
      form.reset();
    } catch (error) { setMessage(displayError(error)); }
    finally { setBusy(false); }
  }

  async function action(watch: Watch, name: "activate" | "pause" | "archive" | "runs") {
    setBusy(true);
    try {
      if (name === "runs") {
        await apiRequest(`/watches/${watch.id}/runs`, { method: "POST" });
        setMessage(`${watch.name} is queued. Successful sources will remain even if one fails.`);
      } else {
        await apiRequest(`/watches/${watch.id}/${name}`, { method: "POST" });
        await load(); setMessage(`${watch.name} was updated.`);
      }
    } catch (error) { setMessage(displayError(error)); }
    finally { setBusy(false); }
  }

  return <>
    <PageHeader eyebrow="Discovery" title="Job Watches" />
    <StatusMessage>{message}</StatusMessage>
    <div className="split-layout">
      <section className="surface" aria-labelledby="new-watch"><h2 id="new-watch">Create a Watch</h2>
        <p className="supporting">Target is broad, Required is mandatory, and Exclude filters a result. No Profile or CV is needed.</p>
        <form onSubmit={create}>
          <label htmlFor="name">Watch name</label><input id="name" name="name" required maxLength={120} />
          <label htmlFor="targets">Target terms <span>(comma-separated)</span></label><input id="targets" name="targets" required placeholder="Backend engineer, Python" />
          <label htmlFor="required">Required terms</label><input id="required" name="required" placeholder="PostgreSQL" />
          <label htmlFor="excluded">Exclude terms</label><input id="excluded" name="excluded" placeholder="Senior director" />
          <label htmlFor="locations">Locations</label><input id="locations" name="locations" placeholder="Bangkok, Remote APAC" />
          <div className="field-row"><label>Experience target<input name="experience" placeholder="Mid-level" /></label><label>Posted within<select name="age" defaultValue="30"><option value="3">3 days</option><option value="7">7 days</option><option value="14">14 days</option><option value="30">30 days</option></select></label></div>
          <label htmlFor="adapter">Public source</label><select id="adapter" name="adapter">{adapters.map(([value, label]) => <option value={value} key={value}>{label}</option>)}</select>
          <label htmlFor="source-url">Documented feed or careers URL</label><input id="source-url" name="source_url" type="url" placeholder="https://…" />
          <button className="button primary" disabled={busy}>Save draft</button>
        </form>
      </section>
      <section className="surface" aria-labelledby="your-watches"><h2 id="your-watches">Your Watches</h2>
        {watches.length === 0 ? <div className="empty"><h3>No Watches yet</h3><p>Create a focused Watch to begin discovery.</p></div> : <ul className="item-list">{watches.map((watch) => <li key={watch.id}><div><span className={`badge ${watch.status.toLowerCase()}`}>{watch.status}</span><h3>{watch.name}</h3><p>{watch.target_terms.join(" · ")}</p></div><div className="row-actions">{watch.status === "DRAFT" && <button onClick={() => action(watch, "activate")} disabled={busy}>Activate</button>}{watch.status === "ACTIVE" && <><button onClick={() => action(watch, "runs")} disabled={busy}>Run now</button><button onClick={() => action(watch, "pause")} disabled={busy}>Pause</button></>}{watch.status === "PAUSED" && <button onClick={() => action(watch, "activate")} disabled={busy}>Resume</button>}<button className="quiet" onClick={() => action(watch, "archive")} disabled={busy}>Archive</button></div></li>)}</ul>}
      </section>
    </div>
  </>;
}
