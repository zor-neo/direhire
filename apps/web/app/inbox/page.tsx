"use client";

import { useCallback, useState } from "react";
import type { components } from "../../../../contracts/generated/api-types";
import { PageHeader, StatusMessage } from "../components/app-shell";
import { apiRequest, displayError } from "../lib/api";
import { useInitialLoad } from "../lib/use-initial-load";

type InboxItem = components["schemas"]["InboxItemRead"];
const statuses = ["NEW", "VIEWED", "SAVED", "INTERESTED", "IGNORED", "ARCHIVED"];

export default function InboxPage() {
  const [items, setItems] = useState<InboxItem[]>([]);
  const [message, setMessage] = useState("Loading matches…");
  const load = useCallback(async () => { try { setItems(await apiRequest<InboxItem[]>("/inbox")); setMessage(""); } catch (error) { setMessage(displayError(error)); } }, []);
  useInitialLoad(load);
  async function update(item: InboxItem, status: string) {
    try { await apiRequest(`/inbox/${item.id}/status`, { method: "PATCH", body: JSON.stringify({ status }) }); await load(); }
    catch (error) { setMessage(displayError(error)); }
  }
  async function track(item: InboxItem) {
    try { await apiRequest("/applications", { method: "POST", body: JSON.stringify({ job_id: item.job_id, status: "APPLIED" }) }); setMessage(`${item.title} was added to Applications.`); }
    catch (error) { setMessage(displayError(error)); }
  }
  return <><PageHeader eyebrow="Deterministic matches" title="Job Inbox" /><StatusMessage>{message}</StatusMessage>
    <section className="surface"><div className="section-heading"><div><h2>Matched roles</h2><p>Watch matches remain visible even when optional Profile Fit is unavailable.</p></div><span className="count">{items.length}</span></div>
      {items.length === 0 ? <div className="empty"><h3>Your Inbox is clear</h3><p>Run an active Watch to discover roles.</p></div> : <ul className="job-list">{items.map((item) => <li key={item.id}><div className="job-main"><div className="job-meta"><span className="meta-chip">{item.company}</span><span className="meta-chip">{item.location || "Location not stated"}</span><span className={`badge ${item.job_lifecycle.toLowerCase()}`}>{item.job_lifecycle.replaceAll("_", " ")}</span></div><h2>{item.title}</h2><p className="supporting">Analysis: {item.analysis_status === "SUCCEEDED" ? "Ready" : item.analysis_status.toLowerCase()}</p>{item.analysis && <details><summary>Structured job analysis</summary><pre>{JSON.stringify(item.analysis, null, 2)}</pre></details>}<button className="text-action" onClick={() => void track(item)}>I applied — track this role</button></div><label className="compact-field">Your status<select value={item.status} onChange={(event) => void update(item, event.target.value)}>{statuses.map((status) => <option key={status}>{status}</option>)}</select></label></li>)}</ul>}
    </section></>;
}
