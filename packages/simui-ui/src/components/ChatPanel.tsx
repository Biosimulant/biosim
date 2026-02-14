import React, { useEffect, useRef, useState } from "react";
import type { ChatAdapter, ChatMessage } from "../types/chat";

function formatTime(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "";
  return date.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

export default function ChatPanel({ adapter }: { adapter: ChatAdapter }) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const endRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    let active = true;
    setLoading(true);
    adapter
      .getThread()
      .then((thread) => {
        if (!active) return;
        setMessages(thread.messages ?? []);
        setError(null);
      })
      .catch((err) => {
        if (!active) return;
        setError(err instanceof Error ? err.message : String(err));
      })
      .finally(() => {
        if (!active) return;
        setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [adapter]);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages.length]);

  const handleSend = async () => {
    const text = input.trim();
    if (!text || sending) return;
    setInput("");
    setSending(true);
    setError(null);

    const now = new Date().toISOString();
    const userMessage: ChatMessage = {
      id: `local-user-${Date.now()}`,
      role: "user",
      content: text,
      createdAt: now,
    };
    const assistantId = `local-assistant-${Date.now()}`;
    const assistantMessage: ChatMessage = {
      id: assistantId,
      role: "assistant",
      content: "",
      createdAt: now,
    };

    setMessages((prev) => [...prev, userMessage, assistantMessage]);

    try {
      const finalMessage = await adapter.sendMessage({
        content: text,
        onChunk: (chunk) => {
          if (!chunk) return;
          setMessages((prev) =>
            prev.map((msg) =>
              msg.id === assistantId ? { ...msg, content: msg.content + chunk } : msg,
            ),
          );
        },
      });
      setMessages((prev) => prev.map((msg) => (msg.id === assistantId ? finalMessage : msg)));
    } catch (err) {
      const message = err instanceof Error ? err.message : String(err);
      setError(message);
      setMessages((prev) => prev.filter((msg) => msg.id !== assistantId));
    } finally {
      setSending(false);
    }
  };

  const onKeyDown: React.KeyboardEventHandler<HTMLTextAreaElement> = (event) => {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      void handleSend();
    }
  };

  return (
    <div className="chat-panel">
      <div className="chat-header">
        <div>
          <div className="chat-title">Simulation Chat</div>
          <div className="chat-subtitle">Shared across related runs.</div>
        </div>
      </div>

      {loading && (
        <div className="chat-loading">Loading chat history…</div>
      )}
      {error && (
        <div className="chat-error">{error}</div>
      )}

      <div className={`chat-messages ${messages.length === 0 ? "empty" : ""}`}>
        {messages.length === 0 && !loading && (
          <div className="chat-empty">Start a conversation about this simulation.</div>
        )}
        {messages.map((msg) => (
          <div key={msg.id} className={`chat-message ${msg.role === "user" ? "user" : "assistant"}`}>
            <div className="chat-bubble">{msg.content}</div>
            <div className="chat-meta">{formatTime(msg.createdAt)}</div>
          </div>
        ))}
        <div ref={endRef} />
      </div>

      <div className="chat-input">
        <textarea
          className="chat-textarea"
          placeholder="Ask about parameters, outputs, or model behavior…"
          value={input}
          onChange={(event) => setInput(event.target.value)}
          onKeyDown={onKeyDown}
          rows={2}
          disabled={sending}
        />
        <button type="button" className="btn btn-primary" onClick={handleSend} disabled={sending || !input.trim()}>
          {sending ? "Sending…" : "Send"}
        </button>
      </div>
    </div>
  );
}
