"use client";

import { useEffect, useRef, useState } from "react";
import { motion } from "framer-motion";
import { Loader2, MessageCircleQuestion, Send, Sparkles } from "lucide-react";
import ReactMarkdown from "react-markdown";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { getChatHistory, streamChat } from "@/lib/api";
import type { ChatMessage } from "@/lib/types";

function MarkdownBubble({ content }: { content: string }) {
  return (
    <div className="prose prose-sm dark:prose-invert max-w-none prose-p:my-1 prose-ul:my-1 prose-headings:my-1.5 prose-headings:text-sm">
      <ReactMarkdown>{content}</ReactMarkdown>
    </div>
  );
}

export function DocChat({
  jobId,
  pendingQuestion,
  onConsumePendingQuestion,
  onJumpToRequirement,
  onJumpToTask,
}: {
  jobId: string;
  pendingQuestion?: string | null;
  onConsumePendingQuestion?: () => void;
  onJumpToRequirement?: (reqId: string) => void;
  onJumpToTask?: (taskId: string) => void;
}) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [question, setQuestion] = useState("");
  const [streamingAnswer, setStreamingAnswer] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [historyLoaded, setHistoryLoaded] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    getChatHistory(jobId)
      .then(setMessages)
      .catch(() => {})
      .finally(() => setHistoryLoaded(true));
  }, [jobId]);

  useEffect(() => {
    if (historyLoaded && pendingQuestion) {
      onConsumePendingQuestion?.();
      handleAsk(pendingQuestion);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [historyLoaded, pendingQuestion]);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [messages, streamingAnswer]);

  async function handleAsk(overrideQuestion?: string) {
    const q = (overrideQuestion ?? question).trim();
    if (!q || loading) return;
    setQuestion("");
    const history = messages.map((m) => ({ role: m.role, content: m.content }));
    setMessages((prev) => [...prev, { role: "user", content: q }]);
    setLoading(true);
    setStreamingAnswer("");

    await streamChat(jobId, q, history, {
      onChunk: (text) => setStreamingAnswer((prev) => (prev ?? "") + text),
      onDone: (payload) => {
        setMessages((prev) => [
          ...prev,
          { role: "assistant", content: payload.answer, citations: payload.citations, followups: payload.followups },
        ]);
        setStreamingAnswer(null);
        setLoading(false);
      },
      onError: () => {
        setMessages((prev) => [...prev, { role: "assistant", content: "Sorry, I couldn't answer that." }]);
        setStreamingAnswer(null);
        setLoading(false);
      },
    });
  }

  const lastMessage = messages[messages.length - 1];
  const showFollowups = !loading && lastMessage?.role === "assistant" && (lastMessage.followups?.length ?? 0) > 0;

  return (
    <div className="flex h-[560px] flex-col rounded-xl border">
      <div className="flex items-center gap-2 border-b p-3">
        <MessageCircleQuestion className="h-4 w-4 text-muted-foreground" />
        <h3 className="text-sm font-semibold">Ask this document</h3>
      </div>

      <div ref={scrollRef} className="flex-1 space-y-3 overflow-y-auto p-4">
        {messages.length === 0 && !streamingAnswer && (
          <p className="text-sm text-muted-foreground">
            Ask anything about the source document — grounded in the actual sections and the analysis, with citations.
          </p>
        )}
        {messages.map((m, i) => (
          <motion.div
            key={i}
            initial={{ opacity: 0, y: 6 }}
            animate={{ opacity: 1, y: 0 }}
            className={m.role === "user" ? "flex justify-end" : "flex justify-start"}
          >
            <div
              className={
                m.role === "user"
                  ? "max-w-[85%] rounded-2xl rounded-br-sm bg-primary px-3.5 py-2 text-sm text-primary-foreground"
                  : "max-w-[85%] rounded-2xl rounded-bl-sm bg-muted px-3.5 py-2 text-sm"
              }
            >
              {m.role === "assistant" ? <MarkdownBubble content={m.content} /> : <p className="whitespace-pre-wrap">{m.content}</p>}
              {m.citations && m.citations.length > 0 && (
                <div className="mt-1.5 flex flex-wrap gap-1">
                  {m.citations.map((c) => {
                    const isReq = /^R-\d+$/.test(c);
                    const isTask = /^T-\d+$/.test(c);
                    if (isReq || isTask) {
                      return (
                        <button
                          key={c}
                          onClick={() => (isReq ? onJumpToRequirement?.(c) : onJumpToTask?.(c))}
                          className="rounded-full border px-2 py-0.5 text-[10px] transition-colors hover:border-brand-accent hover:text-brand-accent"
                        >
                          {c}
                        </button>
                      );
                    }
                    return (
                      <Badge key={c} variant="outline" className="text-[10px]">
                        {c}
                      </Badge>
                    );
                  })}
                </div>
              )}
            </div>
          </motion.div>
        ))}

        {streamingAnswer !== null && (
          <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="flex justify-start">
            <div className="max-w-[85%] rounded-2xl rounded-bl-sm bg-muted px-3.5 py-2 text-sm">
              {streamingAnswer ? (
                <MarkdownBubble content={streamingAnswer} />
              ) : (
                <div className="flex items-center gap-2 text-muted-foreground">
                  <Loader2 className="h-3.5 w-3.5 animate-spin" />
                  Thinking...
                </div>
              )}
            </div>
          </motion.div>
        )}

        {showFollowups && (
          <motion.div initial={{ opacity: 0, y: 4 }} animate={{ opacity: 1, y: 0 }} className="flex flex-wrap gap-1.5 pt-1">
            {lastMessage.followups!.map((fq) => (
              <button
                key={fq}
                onClick={() => handleAsk(fq)}
                className="flex items-center gap-1 rounded-full border bg-background px-2.5 py-1 text-xs text-muted-foreground transition-colors hover:border-primary/50 hover:text-foreground"
              >
                <Sparkles className="h-3 w-3" />
                {fq}
              </button>
            ))}
          </motion.div>
        )}
      </div>

      <div className="flex gap-2 border-t p-3">
        <Input
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && handleAsk()}
          placeholder="e.g. What data sources feed the Account dataset?"
          disabled={loading}
        />
        <Button size="icon" onClick={() => handleAsk()} disabled={loading || !question.trim()}>
          <Send className="h-4 w-4" />
        </Button>
      </div>
    </div>
  );
}
