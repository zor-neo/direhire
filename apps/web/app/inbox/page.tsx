"use client";

import { useCallback, useMemo, useState } from "react";
import type { components } from "../../../../contracts/generated/api-types";

import { JobAnalysisView } from "../../components/JobAnalysisView";
import { toJobAnalysisViewModel } from "../../lib/job-analysis-view-model";
import { PageHeader, StatusMessage } from "../components/app-shell";
import { apiRequest, displayError } from "../lib/api";
import { useInitialLoad } from "../lib/use-initial-load";

type InboxItem = components["schemas"]["InboxItemRead"];
const statuses = ["NEW", "VIEWED", "SAVED", "INTERESTED", "IGNORED", "ARCHIVED"];

function sourceLabel(url: string) {
  try {
    const host = new URL(url).hostname.replace(/^www\./, "");
    if (host === "remotive.com") return "View on Remotive";
    if (host === "usajobs.gov") return "View on USAJOBS";
    if (host.includes("jobthai")) return "View on JobThai";
    if (host.includes("jobstreet")) return "View on JobStreet";
    return `View original on ${host}`;
  } catch {
    return "View original listing";
  }
}

export default function InboxPage() {
  const [items, setItems] = useState<InboxItem[]>([]);
  const [selectedWatchId, setSelectedWatchId] = useState<string>("ALL");
  const [message, setMessage] = useState("Loading matches…");

  const load = useCallback(async () => {
    try {
      setItems(await apiRequest<InboxItem[]>("/inbox"));
      setMessage("");
    } catch (error) {
      setMessage(displayError(error));
    }
  }, []);
  useInitialLoad(load);

  // Extract unique watches present in the matched items
  const watchOptions = useMemo(() => {
    const map = new Map<string, { id: string; name: string; count: number }>();
    for (const item of items) {
      const watches = item.matched_watches || [];
      for (const w of watches) {
        const existing = map.get(w.id);
        if (existing) {
          existing.count += 1;
        } else {
          map.set(w.id, { id: w.id, name: w.name, count: 1 });
        }
      }
    }
    return Array.from(map.values());
  }, [items]);

  // Filter items by selected watch
  const filteredItems = useMemo(() => {
    if (selectedWatchId === "ALL") return items;
    return items.filter((item) =>
      (item.matched_watches || []).some((w) => w.id === selectedWatchId)
    );
  }, [items, selectedWatchId]);

  async function update(item: InboxItem, newStatus: string) {
    try {
      await apiRequest(`/inbox/${item.id}/status`, {
        method: "PATCH",
        body: JSON.stringify({ status: newStatus }),
      });
      await load();
    } catch (error) {
      setMessage(displayError(error));
    }
  }

  async function retryAnalysis(item: InboxItem) {
    try {
      setMessage(`Requesting analysis retry for ${item.title}…`);
      const updated = await apiRequest<InboxItem>(`/inbox/${item.id}/retry-analysis`, {
        method: "POST",
      });
      setItems((prev) => prev.map((it) => (it.id === item.id ? updated : it)));
      setMessage(`Analysis queued for ${item.title}.`);
    } catch (error) {
      setMessage(displayError(error));
    }
  }

  async function track(item: InboxItem) {
    try {
      await apiRequest("/applications", {
        method: "POST",
        body: JSON.stringify({ job_id: item.job_id, status: "APPLIED" }),
      });
      setMessage(`${item.title} was added to Applications.`);
    } catch (error) {
      setMessage(displayError(error));
    }
  }

  async function purge(item: InboxItem) {
    try {
      await apiRequest(`/inbox/${item.id}`, { method: "DELETE" });
      setItems((prev) => prev.filter((it) => it.id !== item.id));
      setMessage(`${item.title} removed from inbox.`);
    } catch (error) {
      setMessage(displayError(error));
    }
  }

  return (
    <>
      <PageHeader eyebrow="Deterministic matches" title="Job Inbox" />
      <StatusMessage>{message}</StatusMessage>

      {watchOptions.length > 0 && (
        <section className="surface" style={{ marginBottom: "1.25rem", padding: "1rem" }}>
          <div style={{ display: "flex", alignItems: "center", gap: "0.75rem", flexWrap: "wrap" }}>
            <span style={{ fontWeight: 600, fontSize: "0.9rem", color: "var(--muted)" }}>
              Filter by Watch:
            </span>
            <button
              type="button"
              className={`button ${selectedWatchId === "ALL" ? "primary" : "secondary"}`}
              style={{ fontSize: "0.85rem", padding: "0.35rem 0.85rem" }}
              onClick={() => setSelectedWatchId("ALL")}
            >
              All Matches ({items.length})
            </button>
            {watchOptions.map((watch) => (
              <button
                key={watch.id}
                type="button"
                className={`button ${selectedWatchId === watch.id ? "primary" : "secondary"}`}
                style={{ fontSize: "0.85rem", padding: "0.35rem 0.85rem" }}
                onClick={() => setSelectedWatchId(watch.id)}
              >
                🎯 {watch.name} ({watch.count})
              </button>
            ))}
          </div>
        </section>
      )}

      <section className="surface">
        <div className="section-heading">
          <div>
            <h2>
              {selectedWatchId === "ALL"
                ? "All Matched Roles"
                : `Matches for: ${watchOptions.find((w) => w.id === selectedWatchId)?.name || "Selected Watch"}`}
            </h2>
            <p>Watch matches remain visible even when optional Profile Fit is unavailable.</p>
          </div>
          <span className="count">{filteredItems.length}</span>
        </div>

        {filteredItems.length === 0 ? (
          <div className="empty">
            <h3>No matches found for this selection</h3>
            <p>
              {selectedWatchId !== "ALL"
                ? "Try selecting 'All Matches' or running a fresh scan for this Watch."
                : "Run an active Watch to discover roles."}
            </p>
          </div>
        ) : (
          <ul className="job-list">
            {filteredItems.map((item) => {
              const vm = toJobAnalysisViewModel(
                item.analysis as Record<string, unknown> | null,
                item.source_url ?? undefined,
              );
              return (
                <li key={item.id}>
                  <div className="job-main">
                    <div className="job-meta" style={{ display: "flex", gap: "0.5rem", flexWrap: "wrap", alignItems: "center" }}>
                      {item.matched_watches && item.matched_watches.length > 0 && (
                        item.matched_watches.map((w) => (
                          <span
                            key={w.id}
                            className="meta-chip"
                            style={{
                              backgroundColor: "var(--accent-soft)",
                              color: "var(--accent)",
                              borderColor: "var(--accent)",
                              fontWeight: 600,
                            }}
                          >
                            🎯 {w.name}
                          </span>
                        ))
                      )}
                      <span className="meta-chip">{item.company}</span>
                      <span className="meta-chip">{item.location || "Location not stated"}</span>
                      <span className={`badge ${item.job_lifecycle.toLowerCase()}`}>
                        {item.job_lifecycle.replaceAll("_", " ")}
                      </span>
                    </div>
                    <h2>{item.title}</h2>
                    <div style={{ display: "flex", alignItems: "center", gap: "0.75rem", margin: "0.25rem 0 0.5rem" }}>
                      <p className="supporting" style={{ margin: 0 }}>
                        Analysis:{" "}
                        <span
                          style={{
                            fontWeight: 600,
                            color:
                              item.analysis_status === "SUCCEEDED"
                                ? "var(--success)"
                                : item.analysis_status === "QUEUED" || item.analysis_status === "RUNNING"
                                ? "var(--warning)"
                                : "var(--danger)",
                          }}
                        >
                          {item.analysis_status === "SUCCEEDED" ? "Ready" : item.analysis_status.toLowerCase()}
                        </span>
                      </p>
                      {item.analysis_status !== "SUCCEEDED" && (
                        <button
                          type="button"
                          style={{
                            display: "inline-flex",
                            alignItems: "center",
                            gap: "0.3rem",
                            fontSize: "0.8rem",
                            fontWeight: 600,
                            padding: "0.2rem 0.65rem",
                            borderRadius: "6px",
                            border: "1px solid var(--line-strong)",
                            background: "var(--card)",
                            color: "var(--ink)",
                            cursor: "pointer",
                            boxShadow: "var(--shadow-sm)",
                          }}
                          onClick={() => void retryAnalysis(item)}
                          title="Retry structured AI job analysis"
                        >
                          <span>🔄</span> Retry analysis
                        </button>
                      )}
                    </div>
                    {item.source_url && (
                      <a
                        className="text-action source-link"
                        href={item.source_url}
                        target="_blank"
                        rel="noreferrer"
                      >
                        {sourceLabel(item.source_url)}
                      </a>
                    )}
                    {vm && (
                      <div style={{ marginTop: "1rem" }}>
                        <JobAnalysisView viewModel={vm} />
                      </div>
                    )}
                    <div style={{ display: "flex", gap: "0.5rem", marginTop: "0.75rem", flexWrap: "wrap" }}>
                      <button className="text-action" onClick={() => void track(item)}>
                        I applied — track this role
                      </button>
                      <button
                        className="text-action"
                        onClick={() => void purge(item)}
                        title="Remove from inbox"
                        aria-label="Remove from inbox"
                        style={{ display: "inline-flex", alignItems: "center", gap: "0.3rem", color: "var(--danger)" }}
                      >
                        <svg
                          width="14"
                          height="14"
                          viewBox="0 0 24 24"
                          fill="none"
                          stroke="currentColor"
                          strokeWidth="2"
                          strokeLinecap="round"
                          strokeLinejoin="round"
                        >
                          <polyline points="3 6 5 6 21 6" />
                          <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2" />
                          <line x1="10" y1="11" x2="10" y2="17" />
                          <line x1="14" y1="11" x2="14" y2="17" />
                        </svg>
                        Remove
                      </button>
                    </div>
                  </div>
                  <label className="compact-field">
                    Your status
                    <select
                      value={item.status}
                      onChange={(event) => void update(item, event.target.value)}
                    >
                      {statuses.map((s) => (
                        <option key={s}>{s}</option>
                      ))}
                    </select>
                  </label>
                </li>
              );
            })}
          </ul>
        )}
      </section>
    </>
  );
}
