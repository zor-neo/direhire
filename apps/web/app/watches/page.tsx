"use client";

import { FormEvent, useCallback, useEffect, useState } from "react";
import type { components } from "../../../../contracts/generated/api-types";

import { PageHeader, StatusMessage } from "../components/app-shell";
import { PlatformCard, type SearchPlatform } from "../components/platform-cards";
import { apiRequest, commaList, displayError } from "../lib/api";
import { detectAdapter } from "../lib/detect-adapter";
import { useInitialLoad } from "../lib/use-initial-load";

type Watch = components["schemas"]["WatchRead"];
type ExternalSearch = components["schemas"]["ExternalSearchRead"];

const experienceLevels = [
  ["ANY", "Any experience"],
  ["ENTRY", "Entry level"],
  ["JUNIOR", "Junior"],
  ["MID", "Mid-level"],
  ["SENIOR", "Senior"],
  ["LEAD", "Lead"],
  ["EXECUTIVE", "Executive"],
];

const workArrangements = [
  ["ON_SITE", "On-site"],
  ["HYBRID", "Hybrid"],
  ["REMOTE", "Remote"],
];

const employmentTypes = [
  ["FULL_TIME", "Full-time"],
  ["PART_TIME", "Part-time"],
  ["CONTRACT", "Contract"],
  ["TEMPORARY", "Temporary"],
  ["INTERNSHIP", "Internship"],
  ["FREELANCE", "Freelance / project"],
];

export default function WatchesPage() {
  const [watches, setWatches] = useState<Watch[]>([]);
  const [platforms, setPlatforms] = useState<SearchPlatform[]>([]);
  const [recommendedKeys, setRecommendedKeys] = useState<Set<string>>(new Set());
  const [selectedPlatforms, setSelectedPlatforms] = useState<string[]>([]);
  const [customUrls, setCustomUrls] = useState([""]);
  const [role, setRole] = useState("");
  const [location, setLocation] = useState("");
  const [message, setMessage] = useState("Loading Watches…");
  const [busy, setBusy] = useState(false);
  const [externalByWatch, setExternalByWatch] = useState<Record<string, ExternalSearch[]>>({});
  const [expandedExternal, setExpandedExternal] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      const [watchValues, platformValues] = await Promise.all([
        apiRequest<Watch[]>("/watches"),
        apiRequest<SearchPlatform[]>("/watches/platforms"),
      ]);
      setWatches(watchValues);
      setPlatforms(platformValues);
      setRecommendedKeys(new Set(platformValues.map((platform) => platform.key)));
      setMessage("");
    } catch (error) {
      setMessage(displayError(error));
    }
  }, []);
  useInitialLoad(load);

  useEffect(() => {
    const firstLocation = commaList(location)[0];
    if (!firstLocation) return;
    const timer = window.setTimeout(async () => {
      try {
        const values = await apiRequest<SearchPlatform[]>(
          `/watches/platforms?location=${encodeURIComponent(firstLocation)}`,
        );
        setRecommendedKeys(new Set(values.map((platform) => platform.key)));
      } catch {
        setRecommendedKeys(new Set());
      }
    }, 350);
    return () => window.clearTimeout(timer);
  }, [location, platforms]);

  function togglePlatform(key: string) {
    setSelectedPlatforms((current) => {
      if (current.includes(key)) return current.filter((value) => value !== key);
      return current.length < 3 ? [...current, key] : current;
    });
  }

  function updateCustomUrl(index: number, value: string) {
    setCustomUrls((current) => current.map((url, item) => (item === index ? value : url)));
  }

  async function create(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    const data = new FormData(form);
    const targets = commaList(role);
    const locations = commaList(location);
    const sources = [
      ...selectedPlatforms.map((platformKey) => ({
        source_kind: "PLATFORM",
        platform_key: platformKey,
      })),
      ...customUrls
        .map((url) => url.trim())
        .filter(Boolean)
        .map((url) => ({
          source_kind: "CUSTOM_URL",
          adapter_key: detectAdapter(url)?.key ?? "generic_public",
          url,
        })),
    ];
    const age = String(data.get("age") ?? "30");
    setBusy(true);
    try {
      const created = await apiRequest<Watch>("/watches", {
        method: "POST",
        body: JSON.stringify({
          target_terms: targets,
          required_terms: commaList(data.get("required")),
          excluded_terms: commaList(data.get("excluded")),
          locations,
          experience_level: data.get("experience") || "ANY",
          posting_age_days: age === "ANY" ? null : Number(age),
          work_arrangements: data.getAll("work_arrangements"),
          employment_types: data.getAll("employment_types"),
          sources,
        }),
      });
      setWatches((current) => [...current, created]);
      setMessage(`${created.name} was created. Activate it when ready to start discovery.`);
      form.reset();
      setRole("");
      setLocation("");
      setSelectedPlatforms([]);
      setCustomUrls([""]);
    } catch (error) {
      setMessage(displayError(error));
    } finally {
      setBusy(false);
    }
  }

  async function action(watch: Watch, name: "activate" | "pause" | "archive" | "runs") {
    setBusy(true);
    try {
      if (name === "runs") {
        await apiRequest(`/watches/${watch.id}/runs`, { method: "POST" });
        setMessage(`${watch.name} is queued. Successful sources remain even if one fails.`);
      } else {
        await apiRequest(`/watches/${watch.id}/${name}`, { method: "POST" });
        await load();
        setMessage(`${watch.name} was updated.`);
      }
    } catch (error) {
      setMessage(displayError(error));
    } finally {
      setBusy(false);
    }
  }

  async function deleteWatch(watch: Watch) {
    try {
      await apiRequest(`/watches/${watch.id}`, { method: "DELETE" });
      setWatches((current) => current.filter((w) => w.id !== watch.id));
      setMessage(`${watch.name} was deleted.`);
    } catch (error) {
      setMessage(displayError(error));
    }
  }

  async function toggleExternalSearch(watch: Watch) {
    if (expandedExternal === watch.id) {
      setExpandedExternal(null);
      return;
    }
    setExpandedExternal(watch.id);
    if (externalByWatch[watch.id]) return;
    try {
      const searches = await apiRequest<ExternalSearch[]>(
        `/watches/${watch.id}/external-searches`,
      );
      setExternalByWatch((current) => ({ ...current, [watch.id]: searches }));
    } catch (error) {
      setExpandedExternal(null);
      setMessage(displayError(error));
    }
  }

  const autoName = [commaList(role)[0], commaList(location)[0]].filter(Boolean).join(" · ");
  const hasLocation = Boolean(commaList(location)[0]);
  const recommended = platforms.filter(
    (platform) => !hasLocation || recommendedKeys.has(platform.key),
  );
  const alsoAvailable = hasLocation
    ? platforms.filter((platform) => !recommendedKeys.has(platform.key))
    : [];

  return (
    <>
      <PageHeader eyebrow="Discovery" title="Job Watches" />
      <StatusMessage>{message}</StatusMessage>
      <div className="watch-layout">
        <section className="surface watch-builder" aria-labelledby="new-watch">
          <div className="section-heading">
            <div>
              <h2 id="new-watch">Create a Watch</h2>
              <p>Describe the work you want. DireHire handles the source details.</p>
            </div>
          </div>
          <form onSubmit={create}>
            <fieldset className="watch-section">
              <legend>What are you looking for?</legend>
              <label htmlFor="targets">
                What role?
                <input
                  id="targets"
                  value={role}
                  onChange={(event) => setRole(event.target.value)}
                  required
                  placeholder="IT support, Backend engineer"
                  aria-describedby="targets-hint"
                />
              </label>
              <p className="hint" id="targets-hint">Separate alternative roles with commas.</p>
              <div className="field-row">
                <label htmlFor="locations">
                  Where?
                  <input
                    id="locations"
                    value={location}
                    onChange={(event) => setLocation(event.target.value)}
                    placeholder="Bangkok, Remote APAC"
                  />
                </label>
                <label htmlFor="experience">
                  Experience level
                  <select id="experience" name="experience" defaultValue="ANY">
                    {experienceLevels.map(([value, label]) => (
                      <option value={value} key={value}>{label}</option>
                    ))}
                  </select>
                </label>
              </div>
              {autoName && <p className="auto-name">Watch name: <strong>{autoName}</strong></p>}

              <details className="collapsible">
                <summary>More options</summary>
                <div className="collapsible-content">
                  <label htmlFor="required">Required terms<input id="required" name="required" placeholder="PostgreSQL" /></label>
                  <label htmlFor="excluded">Exclude terms<input id="excluded" name="excluded" placeholder="Director, unpaid" /></label>
                  <div>
                    <span className="field-label">Work arrangement</span>
                    <div className="choice-grid">
                      {workArrangements.map(([value, label]) => <label className="check" key={value}><input type="checkbox" name="work_arrangements" value={value} />{label}</label>)}
                    </div>
                  </div>
                  <div>
                    <span className="field-label">Employment type</span>
                    <div className="choice-grid">
                      {employmentTypes.map(([value, label]) => <label className="check" key={value}><input type="checkbox" name="employment_types" value={value} />{label}</label>)}
                    </div>
                  </div>
                  <label htmlFor="age">Posted within<select id="age" name="age" defaultValue="30"><option value="3">3 days</option><option value="7">7 days</option><option value="14">14 days</option><option value="30">30 days</option><option value="ANY">Any available</option></select></label>
                </div>
              </details>
            </fieldset>

            <fieldset className="watch-section">
              <legend>Where should we search?</legend>
              <p className="supporting">Choose up to three platforms. Availability is based on tested public access.</p>
              {recommended.length > 0 && <>
                <h3 className="platform-group-title">Recommended for this location</h3>
                <div className="platform-grid">
                  {recommended.map((platform) => <PlatformCard key={platform.key} platform={platform} selected={selectedPlatforms.includes(platform.key)} disabled={selectedPlatforms.length >= 3 && !selectedPlatforms.includes(platform.key)} onToggle={togglePlatform} />)}
                </div>
              </>}
              {alsoAvailable.length > 0 && <>
                <h3 className="platform-group-title">Also available</h3>
                <div className="platform-grid">
                  {alsoAvailable.map((platform) => <PlatformCard key={platform.key} platform={platform} selected={selectedPlatforms.includes(platform.key)} disabled={selectedPlatforms.length >= 3 && !selectedPlatforms.includes(platform.key)} onToggle={togglePlatform} />)}
                </div>
              </>}
              {platforms.length === 0 && <p className="empty-inline">No tested search platform is available right now. You can still add company career pages below.</p>}
              {selectedPlatforms.length > 0 && <div className="chip-row" aria-label="Selected platforms">{selectedPlatforms.map((key) => { const platform = platforms.find((item) => item.key === key); return <button type="button" className="meta-chip" key={key} onClick={() => togglePlatform(key)}>{platform?.name ?? key}<span aria-hidden="true">×</span></button>; })}</div>}
            </fieldset>

            <details className="collapsible watch-section">
              <summary>Watch a specific company&apos;s career page</summary>
              <div className="collapsible-content">
                <p className="supporting">Optional. Add up to two public career-page URLs.</p>
                {customUrls.map((url, index) => {
                  const detected = detectAdapter(url);
                  return <div className="url-input-group" key={index}><label htmlFor={`custom-url-${index}`}>Company career URL<input id={`custom-url-${index}`} type="url" value={url} onChange={(event) => updateCustomUrl(index, event.target.value)} placeholder="https://company.example/careers" /></label>{url && <span className={`detection-label ${detected ? "detected" : "generic"}`}>{detected ? `Detected: ${detected.label}` : "Public page detection"}</span>}{customUrls.length > 1 && <button type="button" className="quiet" onClick={() => setCustomUrls((current) => current.filter((_, item) => item !== index))}>Remove</button>}</div>;
                })}
                {customUrls.length < 2 && <button type="button" className="quiet add-url" onClick={() => setCustomUrls((current) => [...current, ""])}>+ Add another URL</button>}
              </div>
            </details>

            <button className="button primary create-watch-button" disabled={busy || commaList(role).length === 0}>Create Watch</button>
          </form>
        </section>

        <section className="surface" aria-labelledby="your-watches">
          <h2 id="your-watches">Your Watches</h2>
          {watches.length === 0 ? (
            <div className="empty"><h3>No Watches yet</h3><p>Create a focused Watch to begin discovery.</p></div>
          ) : (
            <ul className="item-list watch-list">
              {watches.map((watch) => (
                <li className="watch-item" key={watch.id}>
                  <div className="watch-item-summary">
                    <div>
                      <span className={`badge ${watch.status.toLowerCase()}`}>{watch.status}</span>
                      <h3>{watch.name}</h3>
                      <p>{watch.target_terms.join(" · ")}</p>
                    </div>
                    <div className="row-actions">
                      {watch.status === "DRAFT" && <button onClick={() => action(watch, "activate")} disabled={busy}>Activate</button>}
                      {watch.status === "ACTIVE" && <><button onClick={() => action(watch, "runs")} disabled={busy}>Run now</button><button onClick={() => action(watch, "pause")} disabled={busy}>Pause</button></>}
                      {watch.status === "PAUSED" && <button onClick={() => action(watch, "activate")} disabled={busy}>Resume</button>}
                      <button
                        aria-expanded={expandedExternal === watch.id}
                        onClick={() => void toggleExternalSearch(watch)}
                      >
                        Search externally
                      </button>
                      <button className="quiet" onClick={() => action(watch, "archive")} disabled={busy}>Archive</button>
                      <button
                        className="quiet"
                        onClick={() => void deleteWatch(watch)}
                        title="Delete watch"
                        aria-label="Delete watch"
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
                        Delete
                      </button>
                    </div>
                  </div>
                  {expandedExternal === watch.id && (
                    <div className="external-search-panel">
                      <p>
                        These links open third-party sites. DireHire does not retrieve or store
                        their results. Your target role and first location are included in search
                        links when the site supports them.
                      </p>
                      {!externalByWatch[watch.id] ? (
                        <span className="supporting">Preparing links…</span>
                      ) : (
                        <div className="external-search-grid">
                          {externalByWatch[watch.id].map((search) => (
                            <a key={search.key} href={search.url} target="_blank" rel="noreferrer">
                              <strong>{search.name}</strong>
                              <span>{search.coverage}</span>
                            </a>
                          ))}
                        </div>
                      )}
                    </div>
                  )}
                </li>
              ))}
            </ul>
          )}
        </section>
      </div>
    </>
  );
}
