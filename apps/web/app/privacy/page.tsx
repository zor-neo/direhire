"use client";

import { useCallback, useState } from "react";
import type { components } from "../../../../contracts/generated/api-types";
import { PageHeader, StatusMessage } from "../components/app-shell";
import { apiRequest, displayError } from "../lib/api";
import { useInitialLoad } from "../lib/use-initial-load";

type Export = components["schemas"]["ExportRead"];
type Deletion = components["schemas"]["DeletionRead"];

export default function PrivacyPage() {
  const [exports, setExports] = useState<Export[]>([]); const [deletions, setDeletions] = useState<Deletion[]>([]); const [message, setMessage] = useState("");
  const load = useCallback(async () => { try { const [exportItems, deletionItems] = await Promise.all([apiRequest<Export[]>("/privacy/exports"), apiRequest<Deletion[]>("/privacy/deletions")]); setExports(exportItems); setDeletions(deletionItems); } catch (error) { setMessage(displayError(error)); } }, []);
  useInitialLoad(load);
  async function createExport() { try { await apiRequest("/privacy/exports", { method: "POST" }); await load(); setMessage("Private export queued. The download expires automatically."); } catch (error) { setMessage(displayError(error)); } }
  async function download(id: string) { try { const result = await apiRequest<components["schemas"]["ExportDownloadRead"]>(`/privacy/exports/${id}/download`); window.location.assign(result.url); } catch (error) { setMessage(displayError(error)); } }
  async function remove(scope: "CAREER_DATA" | "ACCOUNT") { const required = scope === "ACCOUNT" ? "DELETE MY ACCOUNT" : "DELETE CAREER DATA"; const confirmation = window.prompt(`This is irreversible. Type ${required} to continue.`); if (confirmation !== required) { setMessage("Deletion was not requested."); return; } try { await apiRequest("/privacy/deletions", { method: "POST", body: JSON.stringify({ scope, confirmation }) }); await load(); setMessage(scope === "ACCOUNT" ? "Account deletion started and sessions are being revoked." : "Career-data deletion started."); } catch (error) { setMessage(displayError(error)); } }
  return <><PageHeader eyebrow="Owner-controlled" title="Privacy & Data" /><StatusMessage>{message}</StatusMessage><section className="privacy-grid"><article className="surface"><h2>How your data is handled</h2><dl><dt>Public jobs</dt><dd>May enter the shared corpus after normalization.</dd><dt>Pasted jobs, Profile, CVs, and notes</dt><dd>Private user data. Admins cannot browse the content.</dd><dt>Private AI</dt><dd>Minimum necessary context uses the approved private route. It never falls back to the public AI pool.</dd><dt>Backups</dt><dd>Encrypted logical backups have short operational retention. They are not an account-restore feature.</dd></dl></article><article className="surface"><h2>Download your data</h2><p>Exports are generated asynchronously, stored privately, and expire.</p><button className="button primary" onClick={() => void createExport()}>Create export</button><ul className="plain-list">{exports.map((item) => <li key={item.id}><span>{item.status} · {new Date(item.created_at).toLocaleDateString()}</span>{item.status === "SUCCEEDED" && <button onClick={() => void download(item.id)}>Download</button>}</li>)}</ul></article><article className="surface danger-zone"><h2>Delete data</h2><p>Explicit deletion removes active private career content. Shared public job records are preserved.</p><div className="row-actions"><button onClick={() => void remove("CAREER_DATA")}>Delete career data</button><button className="danger" onClick={() => void remove("ACCOUNT")}>Delete account</button></div><ul className="plain-list">{deletions.map((item) => <li key={item.id}>{item.scope}: {item.status}</li>)}</ul></article></section></>;
}
