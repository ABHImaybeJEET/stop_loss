"use client";

import React, { useState } from "react";
import { Check, ThumbsDown, ThumbsUp } from "lucide-react";
import { deleteFeedback, submitFeedback } from "@/lib/chat/api";
import { Button, cn } from "@/components/ui/primitives";
import type { FeedbackState } from "@/lib/chat/types";

const POSITIVE_TAGS = ["Accurate", "Helpful"] as const;
const NEGATIVE_TAGS = ["Too vague", "Outdated data", "Wrong asset", "Risky advice"] as const;

interface Props {
  threadId: string | null;
  messageId: string;
  feedback?: FeedbackState;
  onChange: (feedback: FeedbackState | undefined) => void;
}

export default function FeedbackBar({ threadId, messageId, feedback, onChange }: Props) {
  const [editing, setEditing] = useState(false);
  const [rating, setRating] = useState<"up" | "down" | null>(feedback?.rating ?? null);
  const [tags, setTags] = useState<string[]>(feedback?.tags ?? []);
  const [comment, setComment] = useState(feedback?.comment ?? "");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const choose = (value: "up" | "down") => {
    setRating(value);
    setEditing(true);
    setError(null);
    setTags((prev) => {
      const allowed = (value === "up" ? POSITIVE_TAGS : NEGATIVE_TAGS) as readonly string[];
      return prev.filter((t) => allowed.includes(t));
    });
  };

  const save = async () => {
    if (!rating || !threadId) return;
    setBusy(true);
    setError(null);
    try {
      const saved = await submitFeedback(threadId, messageId, { rating, tags, comment: comment.trim() || undefined });
      onChange(saved);
      setEditing(false);
    } catch {
      setError("Could not save feedback. Try again.");
    } finally {
      setBusy(false);
    }
  };

  const undo = async () => {
    setBusy(true);
    setError(null);
    try {
      await deleteFeedback(messageId);
      onChange(undefined);
      setRating(null);
      setTags([]);
      setComment("");
    } catch {
      setError("Could not remove feedback.");
    } finally {
      setBusy(false);
    }
  };

  if (feedback && !editing) {
    return (
      <div className="flex flex-wrap items-center gap-2 border border-line bg-canvas px-3 py-2" data-testid="feedback-saved" role="status">
        <Check className="h-3.5 w-3.5 text-gain" aria-hidden="true" />
        <span className="text-xs text-ink">
          Thanks, feedback saved ({feedback.rating === "up" ? "helpful" : "not helpful"}
          {feedback.tags.length ? `: ${feedback.tags.join(", ")}` : ""}).
        </span>
        <span className="ml-auto flex gap-1">
          <Button size="sm" variant="ghost" onClick={() => setEditing(true)} disabled={busy}>
            Edit
          </Button>
          <Button size="sm" variant="ghost" onClick={undo} disabled={busy}>
            Undo
          </Button>
        </span>
        {error && <p className="w-full font-mono text-2xs text-loss">{error}</p>}
      </div>
    );
  }

  return (
    <div className="border border-line px-3 py-2" data-testid="feedback-bar">
      <div className="flex flex-wrap items-center gap-2">
        <span className="font-mono text-2xs uppercase tracking-widest text-muted">Was this useful?</span>
        <div className="flex gap-1">
          {(["up", "down"] as const).map((value) => {
            const Icon = value === "up" ? ThumbsUp : ThumbsDown;
            return (
              <button
                key={value}
                type="button"
                onClick={() => choose(value)}
                aria-pressed={rating === value}
                aria-label={value === "up" ? "Helpful" : "Not helpful"}
                className={cn(
                  "flex h-7 w-7 items-center justify-center border",
                  rating === value ? "border-ink bg-ink text-white" : "border-line-strong text-muted hover:border-ink hover:text-ink",
                )}
                data-testid={`feedback-${value}`}
              >
                <Icon className="h-3.5 w-3.5" aria-hidden="true" />
              </button>
            );
          })}
        </div>
        {editing && rating && (
          <span className="ml-1 font-mono text-2xs italic text-muted">
            {rating === "up" ? "Positive feedback" : "Negative feedback"}
          </span>
        )}
      </div>
      {editing && rating && (
        <div className="mt-2 space-y-2">
          <div role="group" aria-label="Feedback tags" className="flex flex-wrap gap-1.5">
            {(rating === "up" ? POSITIVE_TAGS : NEGATIVE_TAGS).map((tag) => {
              const on = tags.includes(tag);
              return (
                <button
                  key={tag}
                  type="button"
                  aria-pressed={on}
                  onClick={() => setTags((t) => (on ? t.filter((x) => x !== tag) : [...t, tag]))}
                  className={cn(
                    "border px-2 py-1 font-mono text-2xs",
                    on ? "border-ink bg-ink text-white" : "border-line-strong text-muted hover:border-ink hover:text-ink",
                  )}
                >
                  {tag}
                </button>
              );
            })}
          </div>
          <label className="sr-only" htmlFor={`fb-${messageId}`}>
            Optional comment
          </label>
          <textarea
            id={`fb-${messageId}`}
            value={comment}
            onChange={(e) => setComment(e.target.value)}
            maxLength={2000}
            rows={2}
            placeholder="Optional comment"
            className="w-full resize-none border border-line-strong px-2 py-1.5 text-xs text-ink placeholder:text-muted-soft focus:border-ink"
          />
          <div className="flex items-center gap-2">
            <Button size="sm" variant="primary" onClick={save} disabled={busy || !threadId} data-testid="feedback-submit">
              {busy ? "Saving…" : "Submit feedback"}
            </Button>
            <Button size="sm" variant="ghost" onClick={() => setEditing(false)} disabled={busy}>
              Cancel
            </Button>
            {error && <span className="font-mono text-2xs text-loss">{error}</span>}
          </div>
        </div>
      )}
    </div>
  );
}
