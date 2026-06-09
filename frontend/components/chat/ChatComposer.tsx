"use client";

import { FormEvent } from "react";

interface Props {
  value: string;
  onChange: (value: string) => void;
  onSubmit: () => void;
  disabled?: boolean;
}

export function ChatComposer({ value, onChange, onSubmit, disabled }: Props) {
  const handleSubmit = (e: FormEvent) => {
    e.preventDefault();
    onSubmit();
  };

  return (
    <form onSubmit={handleSubmit} className="col">
      <label htmlFor="message-input">Message</label>
      <textarea
        id="message-input"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        rows={4}
        placeholder="Write a message..."
        onKeyDown={(e) => {
          if (e.key === "Enter" && !e.shiftKey) {
            e.preventDefault();
            onSubmit();
          }
        }}
      />
      <button type="submit" disabled={disabled || !value.trim()}>
        {disabled ? "Sending..." : "Send"}
      </button>
    </form>
  );
}
