"use client";

import { FormEvent, useCallback, useState } from "react";
import type { components } from "../../../../contracts/generated/api-types";
import { PageHeader, StatusMessage } from "../components/app-shell";
import { apiRequest, displayError } from "../lib/api";
import { useInitialLoad } from "../lib/use-initial-load";

type Analysis = components["schemas"]["AnalyzeJobRead"];

export default function AnalyzePage() {
  const [items, setItems] = useState<Analysis[]>([]);
  const [mode, setMode] = useState<"PUBLIC_URL" | "PASTED_TEXT">("PUBLIC_URL");
  const [message, setMessage] = useState("Loading recent analyses…");
  const [busy, setBusy] = useState(false);
  const load = useCallback(async () => { try { setItems(await apiRequest<Analysis[]>("/analyze-jobs")); setMessage(""); } catch (error) { setMessage(displayError(error)); } }, []);
  useInitialLoad(load);
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); const form = event.currentTarget; const data = new FormData(form); setBusy(true);
    try { const item = await apiRequest<Analysis>("/analyze-jobs", { method: "POST", body: JSON.stringify({ input_type: mode, url: mode === "PUBLIC_URL" ? data.get("url") : null, text: mode === "PASTED_TEXT" ? data.get("text") : null }) }); setItems((current) => [item, ...current.filter((value) => value.id !== item.id)]); setMessage(mode === "PASTED_TEXT" ? "Private analysis queued. Pasted text will not enter the shared corpus." : "Public job analysis queued."); form.reset(); }
    catch (error) { setMessage(displayError(error)); } finally { setBusy(false); }
  }
  async function action(id: string, actionName: "save" | "watch-draft") { try { await apiRequest(`/analyze-jobs/${id}/${actionName}`, { method: "POST" }); await load(); setMessage(actionName === "save" ? "Saved to your Inbox." : "A draft Watch was created for your review."); } catch (error) { setMessage(displayError(error)); } }
  return <><PageHeader eyebrow="One role at a time" title="Analyze a Job" /><StatusMessage>{message}</StatusMessage><div className="split-layout"><section className="surface"><div className="tabs" role="tablist" aria-label="Job input type"><button role="tab" aria-selected={mode === "PUBLIC_URL"} onClick={() => setMode("PUBLIC_URL")}>Public URL</button><button role="tab" aria-selected={mode === "PASTED_TEXT"} onClick={() => setMode("PASTED_TEXT")}>Paste privately</button></div><form onSubmit={submit}>{mode === "PUBLIC_URL" ? <><label htmlFor="job-url">Public job URL</label><input id="job-url" name="url" type="url" required placeholder="https://company.example/jobs/…" /><p className="hint">Public content may be reused in the shared job corpus.</p></> : <><label htmlFor="job-text">Job description</label><textarea id="job-text" name="text" required minLength={100} rows={14} /><p className="hint">Private user data. Routed only through the approved private AI route and never added to discovery.</p></>}<button className="button primary" disabled={busy}>Analyze job</button></form></section><section className="surface"><h2>Recent analyses</h2>{items.length === 0 ? <div className="empty"><p>No analyses yet.</p></div> : <ul className="item-list">{items.map((item) => <li key={item.id}><div><span className="badge">{item.status}</span><h3>{item.input_type === "PASTED_TEXT" ? "Private pasted job" : item.normalized_url ?? "Public job"}</h3>{item.analysis && <details><summary>View structured analysis</summary><pre>{JSON.stringify(item.analysis, null, 2)}</pre></details>}{item.similar_openings.length > 0 && <p>{item.similar_openings.length} similar opening(s) already known.</p>}</div><div className="row-actions"><button onClick={() => void action(item.id, "save")}>Save</button><button onClick={() => void action(item.id, "watch-draft")}>Create Watch draft</button></div></li>)}</ul>}</section></div></>;
}
