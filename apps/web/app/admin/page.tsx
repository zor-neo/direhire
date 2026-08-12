"use client";

import { useCallback, useState } from "react";
import type { components } from "../../../../contracts/generated/api-types";
import { PageHeader, StatusMessage } from "../components/app-shell";
import { apiRequest, displayError } from "../lib/api";
import { useInitialLoad } from "../lib/use-initial-load";

type Summary = components["schemas"]["OperationsSummary"];
type Policy = components["schemas"]["SourcePolicyRead"];
type Control = components["schemas"]["PlatformControlRead"];

export default function AdminPage() {
  const [summary, setSummary] = useState<Summary | null>(null);
  const [policies, setPolicies] = useState<Policy[]>([]);
  const [controls, setControls] = useState<Control[]>([]);
  const [message, setMessage] = useState("Loading operational metadata…");

  const load = useCallback(async () => {
    try {
      const [nextSummary, nextPolicies, nextControls] = await Promise.all([
        apiRequest<Summary>("/admin/operations/summary"),
        apiRequest<Policy[]>("/admin/source-policies"),
        apiRequest<Control[]>("/admin/operations/controls"),
      ]);
      setSummary(nextSummary);
      setPolicies(nextPolicies);
      setControls(nextControls);
      setMessage("");
    } catch (error) {
      setMessage(displayError(error));
    }
  }, []);

  useInitialLoad(load);

  async function action(
    policy: Policy,
    name: "PAUSE" | "RESUME" | "DISABLE" | "ENABLE" | "CLEAR_FAILURES",
  ) {
    try {
      await apiRequest(`/admin/source-policies/${policy.adapter_key}/actions`, {
        method: "POST",
        body: JSON.stringify({ action: name }),
      });
      await load();
      setMessage(`${policy.adapter_key} updated and audited.`);
    } catch (error) {
      setMessage(displayError(error));
    }
  }

  async function toggle(control: Control) {
    try {
      await apiRequest(`/admin/operations/controls/${control.key}`, {
        method: "PUT",
        body: JSON.stringify({ enabled: !control.enabled }),
      });
      await load();
      setMessage(`${control.key} updated and audited.`);
    } catch (error) {
      setMessage(displayError(error));
    }
  }

  return <>
    <PageHeader eyebrow="Superadmin only" title="Operations" />
    <p className="supporting">Operational metadata only. Private career content is never displayed here.</p>
    <StatusMessage>{message}</StatusMessage>
    {summary && <section className="summary">
      <div><p className="metric">{summary.unpublished_outbox}</p><p>Unpublished events</p></div>
      <div><p className="metric">{summary.active_watch_runs}</p><p>Active Watch runs</p></div>
      <div><p className="metric">{summary.active_ai_operations}</p><p>Active AI operations</p></div>
      <div><p className="metric">{summary.ai_tokens_30d.toLocaleString()}</p><p>AI tokens · 30 days</p></div>
      <div><p className="metric">${(summary.ai_cost_microusd_30d / 1_000_000).toFixed(2)}</p><p>Estimated AI cost · 30 days</p></div>
      <div><p className="metric">{summary.ai_cache_hits_30d}</p><p>AI cache hits · 30 days</p></div>
    </section>}
    <section className="surface">
      <h2>Platform controls</h2>
      <ul className="plain-list">{controls.map((control) => <li key={control.key}>
        <span>{control.key.replaceAll("_", " ")} · {control.enabled ? "Enabled" : "Disabled"}</span>
        <button onClick={() => void toggle(control)}>{control.enabled ? "Disable" : "Enable"}</button>
      </li>)}</ul>
    </section>
    <section className="surface">
      <h2>Source health</h2>
      <div className="table-wrap"><table>
        <thead><tr><th>Adapter</th><th>Health</th><th>Failures</th><th>Access</th><th>Actions</th></tr></thead>
        <tbody>{policies.map((policy) => <tr key={policy.adapter_key}>
          <td>{policy.adapter_key}</td>
          <td><span className="badge">{policy.health}</span></td>
          <td>{policy.failure_count}</td>
          <td>{policy.enabled ? "Enabled" : "Disabled"}</td>
          <td><div className="row-actions">
            <button onClick={() => void action(policy, policy.health === "TEMPORARILY_PAUSED" ? "RESUME" : "PAUSE")}>{policy.health === "TEMPORARILY_PAUSED" ? "Resume" : "Pause"}</button>
            <button onClick={() => void action(policy, policy.enabled ? "DISABLE" : "ENABLE")}>{policy.enabled ? "Disable" : "Enable"}</button>
          </div></td>
        </tr>)}</tbody>
      </table></div>
    </section>
  </>;
}
