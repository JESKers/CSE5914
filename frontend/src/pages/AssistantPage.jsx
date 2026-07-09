import { useEffect, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { resetChat, sendChat } from "@/lib/api";

// Chat UI for the buy/rent AI agent (POST /assistant/chat). The agent runs a
// multi-step tool loop server-side; each turn returns the reply plus the tool
// activity (searches, quotes, bookings) which we render as an activity trail.
// Bot replies are GitHub-flavored markdown (tables, bold, car photos).
// The transcript is kept in sessionStorage so navigating between pages (or a
// refresh in the same tab) doesn't lose the conversation.

const STORAGE_KEY = "jeskers-assistant-chat";

function loadStored() {
  try {
    const raw = sessionStorage.getItem(STORAGE_KEY);
    const data = raw ? JSON.parse(raw) : null;
    return {
      messages: Array.isArray(data?.messages) ? data.messages : [],
      sessionId: data?.sessionId ?? null,
    };
  } catch {
    return { messages: [], sessionId: null };
  }
}

const SUGGESTIONS = [
  "Rent a 7-seater with a child seat in Columbus from Wed to Sun, under $60/day",
  "Rent an SUV in Columbus this weekend, under $70/day, with GPS",
  "I want to buy a family SUV around $40k — compare leasing, buying new, and CPO",
  "Compare leasing vs buying a BMW M4 over 5 years and book me a test drive",
];

function ToolTrail({ events }) {
  if (!events?.length) return null;
  return (
    <div className="chat__trail">
      {events.map((e, i) => (
        <div key={i} className={`chat__tool ${e.is_error ? "chat__tool--err" : ""}`}>
          <span className="chat__tool-name mono">{e.tool}</span>
          <span className="chat__tool-summary">{e.summary}</span>
        </div>
      ))}
    </div>
  );
}

export default function AssistantPage() {
  const [{ messages, sessionId }, setChatState] = useState(loadStored);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const scrollRef = useRef(null);

  useEffect(() => {
    try {
      sessionStorage.setItem(STORAGE_KEY, JSON.stringify({ messages, sessionId }));
    } catch {
      /* storage full/unavailable — chat still works, just not persisted */
    }
  }, [messages, sessionId]);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [messages, busy]);

  async function send(text) {
    const message = (text ?? input).trim();
    if (!message || busy) return;
    setInput("");
    setError(null);
    setChatState((s) => ({ ...s, messages: [...s.messages, { role: "user", text: message }] }));
    setBusy(true);
    try {
      const res = await sendChat({ message, session_id: sessionId });
      setChatState((s) => ({
        sessionId: res.session_id,
        messages: [...s.messages, { role: "bot", text: res.reply, events: res.events }],
      }));
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  async function handleReset() {
    if (sessionId) await resetChat(sessionId).catch(() => {});
    sessionStorage.removeItem(STORAGE_KEY);
    setChatState({ messages: [], sessionId: null });
    setError(null);
  }

  return (
    <div className="shell chat">
      <div className="chat__panel">
        <div className="chat__head">
          <div>
            <h1 className="chat__title">AI Assistant</h1>
            <p className="chat__sub">
              Rentals booked end-to-end · buy decisions with TCO, financing &amp; dealer handoff
            </p>
          </div>
          {messages.length > 0 && (
            <button className="chat__reset mono" onClick={handleReset} disabled={busy}>
              New chat
            </button>
          )}
        </div>

        <div className="chat__messages" ref={scrollRef}>
          {messages.length === 0 && (
            <div className="chat__empty">
              <p className="chat__empty-title">Try one of these:</p>
              {SUGGESTIONS.map((s) => (
                <button key={s} className="chat__suggestion" onClick={() => send(s)}>
                  {s}
                </button>
              ))}
            </div>
          )}
          {messages.map((m, i) => (
            <div key={i} className={`chat__msg chat__msg--${m.role}`}>
              {m.role === "bot" && <ToolTrail events={m.events} />}
              {m.role === "bot" ? (
                <div className="chat__bubble chat__bubble--md">
                  <ReactMarkdown remarkPlugins={[remarkGfm]}>{m.text}</ReactMarkdown>
                </div>
              ) : (
                <div className="chat__bubble">{m.text}</div>
              )}
            </div>
          ))}
          {busy && (
            <div className="chat__msg chat__msg--bot">
              <div className="chat__bubble chat__bubble--typing">
                <span />
                <span />
                <span />
                <em>searching · quoting · booking…</em>
              </div>
            </div>
          )}
          {error && <div className="chat__error">{error}</div>}
        </div>

        <form
          className="chat__inputrow"
          onSubmit={(e) => {
            e.preventDefault();
            send();
          }}
        >
          <input
            className="chat__input"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Describe what you need — rent or buy, budget, dates, seats…"
            disabled={busy}
          />
          <button className="chat__send" type="submit" disabled={busy || !input.trim()}>
            Send
          </button>
        </form>
      </div>
    </div>
  );
}
