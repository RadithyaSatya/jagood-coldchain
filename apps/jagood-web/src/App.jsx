import { useEffect, useRef, useState } from "react";

import {
  DocumentIcon,
  MenuIcon,
  PlusIcon,
  SendIcon,
  SnowflakeIcon,
  StopIcon,
} from "./icons";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "/api";

const SUGGESTIONS = [
  {
    eyebrow: "Tentang Jagood",
    question: "Apa itu Jagood dan bagaimana cara kerjanya?",
  },
  {
    eyebrow: "Fitur utama",
    question: "Apa saja fitur utama yang tersedia di Jagood?",
  },
  {
    eyebrow: "Rantai dingin",
    question: "Jenis distribusi apa saja yang dapat dibantu Jagood?",
  },
];

const WELCOME_MESSAGE = {
  id: "welcome",
  role: "assistant",
  content:
    "Halo, saya Jagood Assistant. Saya siap membantu menjelaskan Jagood dan pengelolaan distribusi cold-chain pangan.",
  handledBy: "rule",
  sources: [],
};

function parseEventBlock(block) {
  const event = block.match(/^event:\s*(.+)$/m)?.[1]?.trim();
  const dataLine = block.match(/^data:\s*(.+)$/m)?.[1];
  if (!event || !dataLine) return null;
  try {
    return { event, data: JSON.parse(dataLine) };
  } catch {
    return null;
  }
}

function sourceLabel(source) {
  const [file, anchor] = source.split("#");
  const title = anchor
    ? anchor.replaceAll("-", " ").replace(/\b\w/g, (letter) => letter.toUpperCase())
    : file;
  return title || file;
}

export default function App() {
  const [messages, setMessages] = useState([WELCOME_MESSAGE]);
  const [input, setInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [isSidebarOpen, setIsSidebarOpen] = useState(false);
  const [serviceStatus, setServiceStatus] = useState("checking");
  const abortRef = useRef(null);
  const textareaRef = useRef(null);
  const endRef = useRef(null);

  useEffect(() => {
    fetch(`${API_BASE_URL}/health`)
      .then((response) => setServiceStatus(response.ok ? "online" : "offline"))
      .catch(() => setServiceStatus("offline"));
  }, []);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  function resizeTextarea() {
    const element = textareaRef.current;
    if (!element) return;
    element.style.height = "auto";
    element.style.height = `${Math.min(element.scrollHeight, 132)}px`;
  }

  function resetChat() {
    abortRef.current?.abort();
    setMessages([WELCOME_MESSAGE]);
    setInput("");
    setIsLoading(false);
    setIsSidebarOpen(false);
    requestAnimationFrame(() => textareaRef.current?.focus());
  }

  async function sendMessage(text = input) {
    const question = text.trim();
    if (!question || isLoading) return;

    const priorMessages = messages
      .filter((message) => message.id !== "welcome" && message.content)
      .slice(-10)
      .map(({ role, content }) => ({ role, content }));
    const userMessage = { id: crypto.randomUUID(), role: "user", content: question };
    const assistantId = crypto.randomUUID();
    const assistantMessage = {
      id: assistantId,
      role: "assistant",
      content: "",
      handledBy: null,
      sources: [],
    };

    setMessages((current) => [...current, userMessage, assistantMessage]);
    setInput("");
    setIsLoading(true);
    setIsSidebarOpen(false);
    if (textareaRef.current) textareaRef.current.style.height = "auto";

    const controller = new AbortController();
    abortRef.current = controller;

    try {
      const response = await fetch(`${API_BASE_URL}/v1/chat/stream`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          language: "id",
          message: question,
          history: priorMessages,
          max_output_tokens: 180,
        }),
        signal: controller.signal,
      });

      if (!response.ok || !response.body) {
        throw new Error(`Server merespons dengan status ${response.status}`);
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";

      while (true) {
        const { value, done } = await reader.read();
        buffer += decoder.decode(value || new Uint8Array(), { stream: !done });
        const blocks = buffer.split("\n\n");
        buffer = blocks.pop() || "";

        for (const block of blocks) {
          const parsed = parseEventBlock(block);
          if (!parsed) continue;
          if (parsed.event === "metadata") {
            setMessages((current) =>
              current.map((message) =>
                message.id === assistantId
                  ? {
                      ...message,
                      handledBy: parsed.data.handled_by,
                      sources: parsed.data.sources || [],
                    }
                  : message,
              ),
            );
          }
          if (parsed.event === "token") {
            setMessages((current) =>
              current.map((message) =>
                message.id === assistantId
                  ? { ...message, content: message.content + (parsed.data.content || "") }
                  : message,
              ),
            );
          }
          if (parsed.event === "error") throw new Error(parsed.data.message);
        }

        if (done) break;
      }
    } catch (error) {
      const wasAborted = error.name === "AbortError";
      setMessages((current) =>
        current.map((message) =>
          message.id === assistantId
            ? {
                ...message,
                content:
                  message.content ||
                  (wasAborted
                    ? "Respons dihentikan."
                    : "Maaf, saya belum dapat terhubung ke layanan Jagood. Silakan coba kembali."),
                isError: !wasAborted,
              }
            : message,
        ),
      );
    } finally {
      abortRef.current = null;
      setIsLoading(false);
      requestAnimationFrame(() => textareaRef.current?.focus());
    }
  }

  function handleKeyDown(event) {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      sendMessage();
    }
  }

  return (
    <div className="app-shell">
      <aside className={`sidebar ${isSidebarOpen ? "sidebar--open" : ""}`}>
        <div className="brand">
          <div className="brand__mark"><SnowflakeIcon /></div>
          <div>
            <strong>JAGOOD</strong>
            <span>ColdChain Intelligence</span>
          </div>
        </div>

        <button className="new-chat" onClick={resetChat} type="button">
          <PlusIcon />
          Percakapan baru
        </button>

        <div className="sidebar__section">
          <p className="sidebar__label">COBA TANYAKAN</p>
          {SUGGESTIONS.map((suggestion) => (
            <button
              className="sidebar-prompt"
              key={suggestion.question}
              onClick={() => sendMessage(suggestion.question)}
              type="button"
            >
              <span>{suggestion.eyebrow}</span>
              {suggestion.question}
            </button>
          ))}
        </div>

        <div className="scope-card">
          <span className="scope-card__icon"><DocumentIcon /></span>
          <div>
            <strong>Berbasis knowledge Jagood</strong>
            <p>Jawaban dirangkum dari dokumentasi yang sudah diverifikasi.</p>
          </div>
        </div>
      </aside>

      {isSidebarOpen && (
        <button className="sidebar-backdrop" onClick={() => setIsSidebarOpen(false)} aria-label="Tutup menu" />
      )}

      <main className="chat-panel">
        <header className="topbar">
          <button className="menu-button" onClick={() => setIsSidebarOpen(true)} aria-label="Buka menu">
            <MenuIcon />
          </button>
          <div className="topbar__title">
            <strong>Jagood Assistant</strong>
            <span>Asisten cold-chain pangan</span>
          </div>
          <div className={`status status--${serviceStatus}`}>
            <span className="status__dot" />
            {serviceStatus === "online" ? "Online" : serviceStatus === "offline" ? "Offline" : "Menghubungkan"}
          </div>
        </header>

        <section className="conversation" aria-live="polite">
          <div className="conversation__inner">
            <div className="day-label"><span>HARI INI</span></div>
            {messages.map((message) => (
              <article className={`message message--${message.role}`} key={message.id}>
                {message.role === "assistant" && (
                  <div className="avatar"><SnowflakeIcon size={18} /></div>
                )}
                <div className="message__body">
                  <div className={`bubble ${message.isError ? "bubble--error" : ""}`}>
                    {message.content || (
                      <span className="typing"><i /><i /><i /></span>
                    )}
                  </div>
                  {message.sources?.length > 0 && (
                    <div className="sources">
                      <span>Sumber</span>
                      {message.sources.map((source) => (
                        <span className="source-chip" key={source} title={source}>
                          <DocumentIcon /> {sourceLabel(source)}
                        </span>
                      ))}
                    </div>
                  )}
                  {message.role === "assistant" && message.handledBy && message.id !== "welcome" && (
                    <span className="response-meta">
                      {message.handledBy === "rule" ? "Jawaban otomatis" : "Dirangkum oleh AI"}
                    </span>
                  )}
                </div>
              </article>
            ))}
            <div ref={endRef} />
          </div>
        </section>

        <footer className="composer-wrap">
          <div className="composer">
            <textarea
              ref={textareaRef}
              value={input}
              onChange={(event) => {
                setInput(event.target.value);
                resizeTextarea();
              }}
              onKeyDown={handleKeyDown}
              placeholder="Tanyakan sesuatu tentang Jagood..."
              rows="1"
              maxLength="1000"
              disabled={isLoading}
              aria-label="Pesan"
            />
            {isLoading ? (
              <button className="send-button send-button--stop" onClick={() => abortRef.current?.abort()} aria-label="Hentikan respons" type="button">
                <StopIcon />
              </button>
            ) : (
              <button className="send-button" onClick={() => sendMessage()} disabled={!input.trim()} aria-label="Kirim pesan" type="button">
                <SendIcon />
              </button>
            )}
          </div>
          <p className="composer-note">Jagood dapat membuat kesalahan. Periksa kembali informasi operasional penting.</p>
        </footer>
      </main>
    </div>
  );
}
