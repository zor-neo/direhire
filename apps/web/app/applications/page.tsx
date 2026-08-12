"use client";

import { FormEvent, useCallback, useState } from "react";
import type { components } from "../../../../contracts/generated/api-types";
import { PageHeader, StatusMessage } from "../components/app-shell";
import { apiRequest, displayError } from "../lib/api";
import { useInitialLoad } from "../lib/use-initial-load";

type Application = components["schemas"]["ApplicationRead"];
type Note = components["schemas"]["NoteRead"];
type Interview = components["schemas"]["InterviewRead"];
type Reminder = components["schemas"]["ReminderRead"];
const statuses = ["APPLIED", "INTERVIEWING", "OFFER", "REJECTED", "WITHDRAWN", "ARCHIVED"];

export default function ApplicationsPage() {
  const [items, setItems] = useState<Application[]>([]);
  const [selected, setSelected] = useState<Application | null>(null);
  const [notes, setNotes] = useState<Note[]>([]);
  const [interviews, setInterviews] = useState<Interview[]>([]);
  const [reminders, setReminders] = useState<Reminder[]>([]);
  const [message, setMessage] = useState("Loading applications…");
  const load = useCallback(async () => {
    try { setItems(await apiRequest<Application[]>("/applications")); setMessage(""); }
    catch (error) { setMessage(displayError(error)); }
  }, []);
  useInitialLoad(load);

  async function open(item: Application) {
    try {
      const [nextNotes, nextInterviews, nextReminders] = await Promise.all([
        apiRequest<Note[]>(`/applications/${item.id}/notes`),
        apiRequest<Interview[]>(`/applications/${item.id}/interviews`),
        apiRequest<Reminder[]>(`/applications/${item.id}/reminders`),
      ]);
      setSelected(item); setNotes(nextNotes); setInterviews(nextInterviews); setReminders(nextReminders);
    } catch (error) { setMessage(displayError(error)); }
  }
  async function add(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); const form = event.currentTarget; const data = new FormData(form);
    try { await apiRequest("/applications", { method: "POST", body: JSON.stringify({ job_id: data.get("job_id"), status: "APPLIED", applied_at: data.get("applied_at") || null }) }); form.reset(); await load(); setMessage("Application added. Status remains under your control."); }
    catch (error) { setMessage(displayError(error)); }
  }
  async function update(item: Application, status: string) {
    try { await apiRequest(`/applications/${item.id}`, { method: "PATCH", body: JSON.stringify({ status, applied_at: item.applied_at }) }); await load(); setSelected({ ...item, status: status as Application["status"] }); }
    catch (error) { setMessage(displayError(error)); }
  }
  async function addNote(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); if (!selected) return; const form = event.currentTarget; const data = new FormData(form);
    try { await apiRequest(`/applications/${selected.id}/notes`, { method: "POST", body: JSON.stringify({ note_type: "OTHER", body: data.get("body") }) }); form.reset(); await open(selected); }
    catch (error) { setMessage(displayError(error)); }
  }
  async function addInterview(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); if (!selected) return; const form = event.currentTarget; const data = new FormData(form);
    try { await apiRequest(`/applications/${selected.id}/interviews`, { method: "POST", body: JSON.stringify({ stage: data.get("stage"), scheduled_at: data.get("scheduled_at") || null, questions_remembered: data.get("questions") || null, went_well: data.get("went_well") || null, difficult: data.get("difficult") || null }) }); form.reset(); await open(selected); }
    catch (error) { setMessage(displayError(error)); }
  }
  async function addReminder(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); if (!selected) return; const form = event.currentTarget; const data = new FormData(form);
    try { await apiRequest(`/applications/${selected.id}/reminders`, { method: "POST", body: JSON.stringify({ reminder_type: "APPLICATION", due_at: data.get("due_at") }) }); form.reset(); await open(selected); }
    catch (error) { setMessage(displayError(error)); }
  }

  return <>
    <PageHeader eyebrow="User-controlled tracking" title="Applications" />
    <StatusMessage>{message}</StatusMessage>
    <section className="surface compact-form"><h2>Add from a saved job</h2><form onSubmit={add}><div className="field-row"><label>Job ID<input name="job_id" required /></label><label>Applied date<input name="applied_at" type="date" /></label></div><button className="button primary">Add application</button></form></section>
    <div className="split-layout">
      <section className="surface"><div className="section-heading"><h2>Your pipeline</h2><span className="count">{items.length}</span></div>{items.length === 0 ? <div className="empty"><p>No tracked applications yet.</p></div> : <ul className="item-list">{items.map((item) => <li key={item.id}><button className="list-select" onClick={() => void open(item)}><span className="eyebrow">{item.company}</span><strong>{item.title}</strong></button><label className="compact-field">Status<select value={item.status} onChange={(event) => void update(item, event.target.value)}>{statuses.map((status) => <option key={status}>{status}</option>)}</select></label></li>)}</ul>}</section>
      <section className="surface"><h2>{selected ? selected.title : "Application workspace"}</h2>{!selected ? <div className="empty"><p>Select an application to add private notes, interview experience, or a reminder.</p></div> : <div className="workspace-stack"><details open><summary>Private notes ({notes.length})</summary><form onSubmit={addNote}><label>Note<textarea name="body" required rows={3} /></label><button>Add note</button></form><ul className="plain-list">{notes.map((note) => <li key={note.id}>{note.body}</li>)}</ul></details><details><summary>Interviews ({interviews.length})</summary><form onSubmit={addInterview}><label>Stage<select name="stage"><option>SCREENING</option><option>TECHNICAL</option><option>FINAL</option><option>OTHER</option></select></label><label>When<input name="scheduled_at" type="datetime-local" /></label><label>Questions remembered<textarea name="questions" rows={2} /></label><label>What went well<textarea name="went_well" rows={2} /></label><label>What was difficult<textarea name="difficult" rows={2} /></label><button>Add interview</button></form></details><details><summary>Reminders ({reminders.length})</summary><form onSubmit={addReminder}><label>Due at<input name="due_at" type="datetime-local" required /></label><button>Add reminder</button></form><ul className="plain-list">{reminders.map((reminder) => <li key={reminder.id}>{new Date(reminder.due_at).toLocaleString()} {reminder.completed_at ? "Completed" : "Due"}</li>)}</ul></details></div>}</section>
    </div>
  </>;
}
