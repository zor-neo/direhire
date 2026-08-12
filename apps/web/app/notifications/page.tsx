"use client";

import { useCallback, useState } from "react";
import type { components } from "../../../../contracts/generated/api-types";
import { PageHeader, StatusMessage } from "../components/app-shell";
import { apiRequest, displayError } from "../lib/api";
import { useInitialLoad } from "../lib/use-initial-load";

type Notification = components["schemas"]["NotificationRead"];

export default function NotificationsPage() {
  const [items, setItems] = useState<Notification[]>([]);
  const [message, setMessage] = useState("Loading notifications…");
  const load = useCallback(async () => {
    try { setItems(await apiRequest<Notification[]>("/notifications")); setMessage(""); }
    catch (error) { setMessage(displayError(error)); }
  }, []);
  useInitialLoad(load);
  async function markRead(item: Notification) {
    try { await apiRequest(`/notifications/${item.id}/read`, { method: "POST" }); await load(); }
    catch (error) { setMessage(displayError(error)); }
  }
  return <><PageHeader eyebrow="In-app source of truth" title="Notifications" /><StatusMessage>{message}</StatusMessage><section className="surface">{items.length === 0 ? <div className="empty"><p>No notifications yet.</p></div> : <ul className="item-list">{items.map((item) => <li key={item.id}><div><span className={`badge ${item.read_at ? "viewed" : "new"}`}>{item.read_at ? "Read" : "New"}</span><h3>{item.title}</h3><p>{item.body}</p><time dateTime={item.created_at}>{new Date(item.created_at).toLocaleString()}</time></div>{!item.read_at && <div className="row-actions"><button onClick={() => void markRead(item)}>Mark read</button></div>}</li>)}</ul>}</section></>;
}
