"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import {
  collection,
  deleteDoc,
  doc,
  getDocs,
  limit,
  orderBy,
  query,
  setDoc,
  writeBatch,
} from "firebase/firestore";
import { db } from "@/lib/firebase";
import { newId, nowIso } from "@/lib/chat/reducer";
import type { AssetRef, ChatMessage, ThreadMeta } from "@/lib/chat/types";

/**
 * Thread persistence: Firestore under users/{uid}/threads/{threadId}/messages/{messageId},
 * with a localStorage cache so a refresh renders instantly (and works if sync fails).
 * The backend separately keeps the agents' conversation memory per thread.
 */

const listKey = (uid: string) => `sl_threads_${uid}`;
const msgKey = (uid: string, threadId: string) => `sl_msgs_${uid}_${threadId}`;

function readLocal<T>(key: string): T | null {
  try {
    const raw = window.localStorage.getItem(key);
    return raw ? (JSON.parse(raw) as T) : null;
  } catch {
    return null;
  }
}

function writeLocal(key: string, value: unknown): void {
  try {
    window.localStorage.setItem(key, JSON.stringify(value));
  } catch {
    // Quota exceeded: the cache is best-effort; Firestore holds the canonical copy.
  }
}

/** Firestore rejects `undefined`; round-trip through JSON to drop it. */
function plain<T>(value: T): T {
  return JSON.parse(JSON.stringify(value)) as T;
}

export function makeTitle(prompt: string, asset: AssetRef): string {
  const text = prompt.replace(/\s+/g, " ").trim();
  return `${asset.symbol} · ${text.length > 48 ? `${text.slice(0, 47)}…` : text}`;
}

function sortThreads(threads: ThreadMeta[]): ThreadMeta[] {
  return [...threads].sort((a, b) => b.updatedAt.localeCompare(a.updatedAt));
}

export function useThreads(uid: string | undefined) {
  const [threads, setThreads] = useState<ThreadMeta[]>([]);
  const [loading, setLoading] = useState(true);
  const [syncError, setSyncError] = useState<string | null>(null);
  const threadsRef = useRef<ThreadMeta[]>([]);
  threadsRef.current = threads;

  const fail = useCallback((err: unknown) => {
    console.warn("Thread sync failed", err);
    setSyncError("Cloud sync unavailable. Threads are saved on this device only.");
  }, []);

  const commitList = useCallback(
    (next: ThreadMeta[]) => {
      const sorted = sortThreads(next);
      threadsRef.current = sorted; // visible to calls in the same tick (create → first save)
      setThreads(sorted);
      if (uid) writeLocal(listKey(uid), sorted);
    },
    [uid],
  );

  useEffect(() => {
    if (!uid) return;
    let cancelled = false;
    const cached = readLocal<ThreadMeta[]>(listKey(uid));
    if (cached) setThreads(sortThreads(cached));
    getDocs(query(collection(db, "users", uid, "threads"), orderBy("updatedAt", "desc"), limit(100)))
      .then((snap) => {
        if (cancelled) return;
        const remote = snap.docs.map((d) => d.data() as ThreadMeta);
        // Keep local-only threads (e.g. created while offline) alongside remote ones.
        const ids = new Set(remote.map((t) => t.id));
        commitList([...remote, ...(cached ?? []).filter((t) => !ids.has(t.id))]);
        setSyncError(null);
      })
      .catch(fail)
      .finally(() => !cancelled && setLoading(false));
    return () => {
      cancelled = true;
    };
  }, [uid, commitList, fail]);

  const createThread = useCallback(
    async (prompt: string, asset: AssetRef): Promise<string> => {
      if (!uid) throw new Error("not_signed_in");
      const now = nowIso();
      const meta: ThreadMeta = { id: newId(), title: makeTitle(prompt, asset), asset, createdAt: now, updatedAt: now, messageCount: 0 };
      commitList([meta, ...threadsRef.current]);
      setDoc(doc(db, "users", uid, "threads", meta.id), plain(meta)).catch(fail);
      return meta.id;
    },
    [uid, commitList, fail],
  );

  const loadMessages = useCallback(
    async (threadId: string): Promise<ChatMessage[]> => {
      if (!uid) return [];
      const cached = readLocal<ChatMessage[]>(msgKey(uid, threadId)) ?? [];
      try {
        const snap = await getDocs(query(collection(db, "users", uid, "threads", threadId, "messages"), orderBy("createdAt")));
        const remote = snap.docs.map((d) => d.data() as ChatMessage);
        if (remote.length >= cached.length) {
          writeLocal(msgKey(uid, threadId), remote);
          return remote;
        }
      } catch (err) {
        fail(err);
      }
      return cached;
    },
    [uid, fail],
  );

  const saveMessage = useCallback(
    (threadId: string, message: ChatMessage) => {
      if (!uid) return;
      const key = msgKey(uid, threadId);
      const cached = readLocal<ChatMessage[]>(key) ?? [];
      const index = cached.findIndex((m) => m.id === message.id);
      const next = index === -1 ? [...cached, message] : cached.map((m) => (m.id === message.id ? message : m));
      writeLocal(key, next);
      const now = nowIso();
      const current = threadsRef.current.find((t) => t.id === threadId);
      const asset = message.kind === "user" || message.kind === "divider" ? message.asset : current?.asset;
      if (current) {
        commitList(threadsRef.current.map((t) => (t.id === threadId ? { ...t, updatedAt: now, messageCount: next.length, asset } : t)));
      }
      setDoc(doc(db, "users", uid, "threads", threadId, "messages", message.id), plain(message)).catch(fail);
      setDoc(doc(db, "users", uid, "threads", threadId), plain({ updatedAt: now, messageCount: next.length, asset }), { merge: true }).catch(fail);
    },
    [uid, commitList, fail],
  );

  const discardMessage = useCallback(
    (threadId: string, messageId: string) => {
      if (!uid) return;
      const key = msgKey(uid, threadId);
      writeLocal(key, (readLocal<ChatMessage[]>(key) ?? []).filter((m) => m.id !== messageId));
      deleteDoc(doc(db, "users", uid, "threads", threadId, "messages", messageId)).catch(fail);
    },
    [uid, fail],
  );

  const renameThread = useCallback(
    (threadId: string, title: string) => {
      const clean = title.trim().slice(0, 120);
      if (!uid || !clean) return;
      commitList(threadsRef.current.map((t) => (t.id === threadId ? { ...t, title: clean } : t)));
      setDoc(doc(db, "users", uid, "threads", threadId), { title: clean }, { merge: true }).catch(fail);
    },
    [uid, commitList, fail],
  );

  const deleteThread = useCallback(
    async (threadId: string) => {
      if (!uid) return;
      commitList(threadsRef.current.filter((t) => t.id !== threadId));
      try {
        window.localStorage.removeItem(msgKey(uid, threadId));
      } catch {
        // ignore
      }
      try {
        const snap = await getDocs(collection(db, "users", uid, "threads", threadId, "messages"));
        const batch = writeBatch(db);
        snap.docs.forEach((d) => batch.delete(d.ref));
        batch.delete(doc(db, "users", uid, "threads", threadId));
        await batch.commit();
      } catch (err) {
        fail(err);
      }
    },
    [uid, commitList, fail],
  );

  return { threads, loading, syncError, createThread, loadMessages, saveMessage, discardMessage, renameThread, deleteThread };
}
