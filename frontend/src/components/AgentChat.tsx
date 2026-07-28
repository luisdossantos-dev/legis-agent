import { useState, useRef, useEffect } from "react";
import { apiClient, type ChatMessage, type DocumentSummary } from "../api/client";
import { t } from "../i18n";

interface AgentChatProps {
  document: DocumentSummary;
}

function AgentChat({ document }: AgentChatProps) {
  const [messages, setMessages] = useState<ChatMessage[]>([
    {
      role: "assistant",
      content: t("chat.welcome", document.filename),
    },
  ]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const handleSend = async () => {
    const query = input.trim();
    if (!query || loading) return;

    const userMessage: ChatMessage = { role: "user", content: query };
    setMessages((prev) => [...prev, userMessage]);
    setInput("");
    setLoading(true);

    try {
      const result = await apiClient.chat(document.id, messages, query);

      const assistantMessage: ChatMessage = {
        role: "assistant",
        content: result.response,
        references: result.references,
      };
      setMessages((prev) => [...prev, assistantMessage]);
    } catch (err) {
      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          content: `Error: ${err instanceof Error ? err.message : t("chat.error")}`,
        },
      ]);
    } finally {
      setLoading(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  return (
    <div className="chat-container">
      <div className="chat-header">
        <h3>{t("chat.title", document.filename)}</h3>
        <p style={{ fontSize: 13, color: "var(--color-text-secondary)", marginTop: 4 }}>
          {t("chat.description")}
        </p>
      </div>

      <div className="chat-messages" role="log" aria-live="polite" aria-label="Chat messages">
        {messages.map((msg, i) => (
          <div key={i} className={`message ${msg.role}`}>
            <div>{msg.content}</div>
            {msg.references && msg.references.length > 0 && (
              <div
                style={{
                  marginTop: 8,
                  fontSize: 12,
                  color: "var(--color-accent)",
                  borderTop: "1px solid var(--color-border)",
                  paddingTop: 8,
                }}
              >
                <strong>{t("chat.references")}</strong>
                <ul style={{ marginTop: 4, paddingLeft: 16 }}>
                  {msg.references.map((ref, j) => (
                    <li key={j}>{ref}</li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        ))}
        {loading && (
          <div className="message assistant loading" role="status">
            {t("chat.thinking")}
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>

      <div className="chat-input-area">
        <input
          className="chat-input"
          type="text"
          placeholder={t("chat.placeholder")}
          aria-label={t("chat.placeholder")}
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          disabled={loading}
        />
        <button
          className="chat-send-btn"
          onClick={handleSend}
          disabled={loading || !input.trim()}
          aria-label={loading ? t("chat.sendingAria") : t("chat.sendAria")}
        >
          {loading ? "..." : t("chat.send")}
        </button>
      </div>
    </div>
  );
}

export default AgentChat;
