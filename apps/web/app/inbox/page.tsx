"use client";

import { useCallback, useMemo, useState } from "react";
import type { components } from "../../../../contracts/generated/api-types";

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

  async function update(item: InboxItem, status: string) {
    try {
      await apiRequest(`/inbox/${item.id}/status`, {
        method: "PATCH",
        body: JSON.stringify({ status }),
      });
      await load();
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
            {filteredItems.map((item) => (
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
                  <p className="supporting">
                    Analysis: {item.analysis_status === "SUCCEEDED" ? "Ready" : item.analysis_status.toLowerCase()}
                  </p>
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
                  {item.analysis && (
                    <details>
                      <summary>Structured job analysis</summary>
                      <pre>{JSON.stringify(item.analysis, null, 2)}</pre>
                    </details>
                  )}
                  <button className="text-action" onClick={() => void track(item)}>
                    I applied — track this role
                  </button>
                </div>
                <label className="compact-field">
                  Your status
                  <select
                    value={item.status}
                    onChange={(event) => void update(item, event.target.value)}
                  >
                    {statuses.map((status) => (
                      <option key={status}>{status}</option>
                    ))}
                  </select>
                </label>
              </li>
            ))}
          </ul>
        )}
      </section>
    </>
  );
}
