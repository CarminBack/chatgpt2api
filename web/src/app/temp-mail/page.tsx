"use client";

import { useMemo, useState } from "react";
import { Inbox, LoaderCircle, MailCheck, RefreshCw, Search } from "lucide-react";

import webConfig from "@/constants/common-env";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { useAuthGuard } from "@/lib/use-auth-guard";
import { getStoredAuthKey } from "@/store/auth";

type MailItem = {
  id?: string;
  from_address?: string;
  to_address?: string;
  subject?: string;
  received_at?: string | number;
  has_attachments?: boolean;
  attachment_count?: number;
};

type JsonObject = Record<string, unknown>;

const defaultApiBase = "https://temp-mail.supermewinyou.workers.dev";
const defaultEmail = "codex-1783503790-52e4b3@mewinyou.shop";

async function postJson<T>(path: string, body: JsonObject): Promise<T> {
  const token = await getStoredAuthKey();
  const baseUrl = webConfig.apiUrl.replace(/\/$/, "");
  const response = await fetch(`${baseUrl}${path}`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify(body),
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    const detail = data?.detail;
    const message = typeof detail?.error === "string" ? detail.error : typeof data?.error === "string" ? data.error : `HTTP ${response.status}`;
    throw new Error(message);
  }
  return data as T;
}

function formatReceivedAt(value: MailItem["received_at"]) {
  if (typeof value === "number") {
    const date = new Date(value * 1000);
    return Number.isNaN(date.getTime()) ? String(value) : date.toLocaleString();
  }
  return String(value || "");
}

function TempMailContent() {
  const [apiBase, setApiBase] = useState(defaultApiBase);
  const [email, setEmail] = useState(defaultEmail);
  const [messageId, setMessageId] = useState("");
  const [status, setStatus] = useState("");
  const [domains, setDomains] = useState<string[]>([]);
  const [messages, setMessages] = useState<MailItem[]>([]);
  const [messageBody, setMessageBody] = useState<JsonObject | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState("");

  const requestBody = useMemo(() => ({ api_base: apiBase.trim() }), [apiBase]);

  const run = async (task: () => Promise<void>) => {
    setIsLoading(true);
    setError("");
    try {
      await task();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setIsLoading(false);
    }
  };

  const checkHealth = () => run(async () => {
    const data = await postJson<{ result: JsonObject }>("/api/temp-mail/vwh/health", requestBody);
    setStatus(JSON.stringify(data.result, null, 2));
  });

  const loadDomains = () => run(async () => {
    const data = await postJson<{ items: string[] }>("/api/temp-mail/vwh/domains", requestBody);
    setDomains(data.items || []);
  });

  const loadMessages = () => run(async () => {
    const data = await postJson<{ items: MailItem[] }>("/api/temp-mail/vwh/messages", { ...requestBody, email: email.trim() });
    setMessages(data.items || []);
  });

  const loadMessageBody = (id = messageId) => run(async () => {
    const data = await postJson<{ item: JsonObject }>("/api/temp-mail/vwh/message", { ...requestBody, message_id: id.trim() });
    setMessageId(id.trim());
    setMessageBody(data.item || null);
  });

  return (
    <section className="space-y-4">
      <div className="flex flex-col gap-1 lg:flex-row lg:items-start lg:justify-between">
        <div className="space-y-1">
          <div className="text-xs font-semibold tracking-[0.18em] text-stone-500 uppercase">Temp Mail</div>
          <h1 className="text-2xl font-semibold tracking-tight">临时邮箱测试</h1>
        </div>
      </div>

      <div className="grid gap-4 xl:grid-cols-[minmax(320px,420px)_1fr]">
        <section className="space-y-4 rounded-lg border border-stone-200 bg-white/80 p-4">
          <div className="space-y-2">
            <label className="text-sm font-medium text-stone-700">API Base</label>
            <Input value={apiBase} onChange={(event) => setApiBase(event.target.value)} className="h-10 rounded-lg border-stone-200 bg-white font-mono text-xs" />
          </div>
          <div className="space-y-2">
            <label className="text-sm font-medium text-stone-700">邮箱地址</label>
            <Input value={email} onChange={(event) => setEmail(event.target.value)} className="h-10 rounded-lg border-stone-200 bg-white font-mono text-xs" />
          </div>
          <div className="space-y-2">
            <label className="text-sm font-medium text-stone-700">Message ID</label>
            <Input value={messageId} onChange={(event) => setMessageId(event.target.value)} className="h-10 rounded-lg border-stone-200 bg-white font-mono text-xs" />
          </div>
          <div className="grid grid-cols-2 gap-2">
            <Button type="button" variant="outline" className="h-10 rounded-lg" onClick={checkHealth} disabled={isLoading}>
              <MailCheck className="size-4" /> 健康
            </Button>
            <Button type="button" variant="outline" className="h-10 rounded-lg" onClick={loadDomains} disabled={isLoading}>
              <RefreshCw className="size-4" /> 域名
            </Button>
            <Button type="button" className="h-10 rounded-lg bg-stone-950 text-white hover:bg-stone-800" onClick={loadMessages} disabled={isLoading}>
              <Search className="size-4" /> 查邮箱
            </Button>
            <Button type="button" variant="outline" className="h-10 rounded-lg" onClick={() => loadMessageBody()} disabled={isLoading || !messageId.trim()}>
              <Inbox className="size-4" /> 正文
            </Button>
          </div>
          {isLoading ? <div className="flex items-center gap-2 text-sm text-stone-500"><LoaderCircle className="size-4 animate-spin" /> 请求中</div> : null}
          {error ? <div className="rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700">{error}</div> : null}
        </section>

        <section className="space-y-4">
          <div className="rounded-lg border border-stone-200 bg-white/80 p-4">
            <div className="mb-3 text-sm font-semibold text-stone-800">状态</div>
            <Textarea readOnly value={status} className="min-h-24 rounded-lg border-stone-200 bg-stone-50 font-mono text-xs" />
          </div>

          <div className="rounded-lg border border-stone-200 bg-white/80 p-4">
            <div className="mb-3 flex items-center justify-between gap-3">
              <div className="text-sm font-semibold text-stone-800">域名</div>
              <div className="text-xs text-stone-500">{domains.length}</div>
            </div>
            <div className="flex flex-wrap gap-2">
              {domains.map((item) => (
                <span key={item} className="rounded-md border border-stone-200 bg-stone-50 px-2 py-1 font-mono text-xs text-stone-700">{item}</span>
              ))}
              {!domains.length ? <span className="text-sm text-stone-400">暂无数据</span> : null}
            </div>
          </div>

          <div className="rounded-lg border border-stone-200 bg-white/80 p-4">
            <div className="mb-3 flex items-center justify-between gap-3">
              <div className="text-sm font-semibold text-stone-800">邮件列表</div>
              <div className="text-xs text-stone-500">{messages.length}</div>
            </div>
            <div className="space-y-2">
              {messages.map((item) => (
                <button key={item.id} type="button" onClick={() => item.id ? loadMessageBody(item.id) : undefined} className="w-full rounded-lg border border-stone-200 bg-stone-50 p-3 text-left transition hover:border-stone-300 hover:bg-white">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <span className="font-mono text-xs text-stone-500">{item.id}</span>
                    <span className="text-xs text-stone-500">{formatReceivedAt(item.received_at)}</span>
                  </div>
                  <div className="mt-1 text-sm font-medium text-stone-900">{item.subject || "(无主题)"}</div>
                  <div className="mt-1 truncate text-xs text-stone-500">{item.from_address} {"->"} {item.to_address}</div>
                </button>
              ))}
              {!messages.length ? <div className="rounded-lg border border-dashed border-stone-200 p-4 text-sm text-stone-400">暂无邮件</div> : null}
            </div>
          </div>

          <div className="rounded-lg border border-stone-200 bg-white/80 p-4">
            <div className="mb-3 text-sm font-semibold text-stone-800">邮件正文 JSON</div>
            <Textarea readOnly value={messageBody ? JSON.stringify(messageBody, null, 2) : ""} className="min-h-72 rounded-lg border-stone-200 bg-stone-50 font-mono text-xs" />
          </div>
        </section>
      </div>
    </section>
  );
}

export default function TempMailPage() {
  const { isCheckingAuth, session } = useAuthGuard(["admin"]);

  if (isCheckingAuth || !session || session.role !== "admin") {
    return (
      <div className="flex min-h-[40vh] items-center justify-center">
        <LoaderCircle className="size-5 animate-spin text-stone-400" />
      </div>
    );
  }

  return <TempMailContent />;
}
