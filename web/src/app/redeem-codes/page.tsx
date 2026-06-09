"use client";

import { useEffect, useState } from "react";
import { CheckCircle2, Copy, LoaderCircle, RefreshCw, Search } from "lucide-react";
import { toast } from "sonner";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import {
  createRedeemCodes,
  fetchRedeemCodes,
  updateRedeemCode,
  verifyRedeemCode,
  type CreatedRedeemCode,
  type RedeemCode,
  type RedeemCodeStatus,
} from "@/lib/api";
import { useAuthGuard } from "@/lib/use-auth-guard";

function formatDateTime(value?: string | null) {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat("zh-CN", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  }).format(date);
}

function statusLabel(status: RedeemCodeStatus) {
  return {
    available: "未兑换",
    redeemed: "已兑换",
    expired: "已过期",
    disabled: "已禁用",
    missing: "不存在",
  }[status] ?? status;
}

function StatusBadge({ status }: { status: RedeemCodeStatus }) {
  if (status === "available") return <Badge variant="success" className="rounded-md">未兑换</Badge>;
  if (status === "redeemed") return <Badge variant="default" className="rounded-md">已兑换</Badge>;
  if (status === "expired" || status === "disabled") return <Badge variant="danger" className="rounded-md">{statusLabel(status)}</Badge>;
  return <Badge variant="secondary" className="rounded-md">{statusLabel(status)}</Badge>;
}

async function copyText(value: string) {
  try {
    await navigator.clipboard.writeText(value);
    toast.success("已复制到剪贴板");
  } catch {
    toast.error("复制失败，请手动复制");
  }
}

function RedeemCodesContent() {
  const [items, setItems] = useState<RedeemCode[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isCreating, setIsCreating] = useState(false);
  const [count, setCount] = useState("1");
  const [imageQuota, setImageQuota] = useState("10");
  const [expiresAt, setExpiresAt] = useState("");
  const [prefix, setPrefix] = useState("RC");
  const [createdCodes, setCreatedCodes] = useState<CreatedRedeemCode[]>([]);
  const [verifyInput, setVerifyInput] = useState("");
  const [verifyResult, setVerifyResult] = useState<string>("");
  const [pendingId, setPendingId] = useState("");

  const load = async () => {
    setIsLoading(true);
    try {
      const data = await fetchRedeemCodes();
      setItems(data.items);
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "加载兑换码失败");
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    void load();
  }, []);

  const handleCreate = async () => {
    setIsCreating(true);
    try {
      const data = await createRedeemCodes({
        count: Math.max(1, Number(count) || 1),
        image_quota: Math.max(1, Number(imageQuota) || 0),
        expires_at: expiresAt ? new Date(expiresAt).toISOString() : null,
        prefix: prefix.trim() || "RC",
      });
      setCreatedCodes(data.items);
      setItems(data.all_items);
      const codes = data.items.map((item) => item.code).join("\n");
      if (codes) {
        void copyText(codes);
      }
      toast.success("兑换码已生成");
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "生成兑换码失败");
    } finally {
      setIsCreating(false);
    }
  };

  const handleVerify = async () => {
    const code = verifyInput.trim();
    if (!code) {
      toast.error("请输入兑换码");
      return;
    }
    try {
      const data = await verifyRedeemCode(code);
      setVerifyResult(JSON.stringify(data, null, 2));
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "查验兑换码失败");
    }
  };

  const handleToggle = async (item: RedeemCode) => {
    setPendingId(item.id);
    try {
      const data = await updateRedeemCode(item.id, { enabled: !item.enabled });
      setItems(data.items);
      toast.success(item.enabled ? "已禁用" : "已启用");
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "更新兑换码失败");
    } finally {
      setPendingId("");
    }
  };

  return (
    <section className="space-y-5">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
        <div className="space-y-1">
          <div className="text-xs font-semibold tracking-[0.18em] text-stone-500 uppercase">Redeem Codes</div>
          <h1 className="text-2xl font-semibold tracking-tight">兑换码管理</h1>
          <p className="text-sm text-stone-500">生成一次性图片额度兑换码，查验状态，并查看兑换到哪个用户。</p>
        </div>
        <Button variant="outline" onClick={() => void load()} disabled={isLoading} className="h-10 rounded-xl border-stone-200 bg-white px-4 text-stone-700">
          <RefreshCw className={`size-4 ${isLoading ? "animate-spin" : ""}`} />
          刷新
        </Button>
      </div>

      <Card className="rounded-2xl border-white/80 bg-white/90 shadow-sm">
        <CardContent className="space-y-4 p-6">
          <div className="grid gap-3 md:grid-cols-[120px_150px_1fr_120px_auto] md:items-end">
            <label className="space-y-2 text-sm font-medium text-stone-700">
              生成数量
              <Input type="number" min="1" max="500" value={count} onChange={(event) => setCount(event.target.value)} className="h-10 rounded-xl border-stone-200 bg-white" />
            </label>
            <label className="space-y-2 text-sm font-medium text-stone-700">
              每码额度
              <Input type="number" min="1" value={imageQuota} onChange={(event) => setImageQuota(event.target.value)} className="h-10 rounded-xl border-stone-200 bg-white" />
            </label>
            <label className="space-y-2 text-sm font-medium text-stone-700">
              过期时间（可空）
              <Input type="datetime-local" value={expiresAt} onChange={(event) => setExpiresAt(event.target.value)} className="h-10 rounded-xl border-stone-200 bg-white" />
            </label>
            <label className="space-y-2 text-sm font-medium text-stone-700">
              前缀
              <Input value={prefix} onChange={(event) => setPrefix(event.target.value)} className="h-10 rounded-xl border-stone-200 bg-white" />
            </label>
            <Button onClick={() => void handleCreate()} disabled={isCreating} className="h-10 rounded-xl bg-stone-950 px-4 text-white hover:bg-stone-800">
              {isCreating ? <LoaderCircle className="size-4 animate-spin" /> : <CheckCircle2 className="size-4" />}
              生成兑换码
            </Button>
          </div>
          {createdCodes.length > 0 ? (
            <div className="rounded-xl border border-emerald-200 bg-emerald-50 p-4 text-sm text-emerald-900">
              <div className="mb-2 font-medium">本次生成的明文兑换码（仅显示一次，请立即保存）：</div>
              <div className="flex items-start justify-between gap-3 rounded-lg bg-white/80 p-3">
                <code className="whitespace-pre-wrap break-all font-mono text-[13px]">{createdCodes.map((item) => item.code).join("\n")}</code>
                <Button variant="outline" className="h-9 shrink-0 rounded-xl border-emerald-200 bg-white px-4 text-emerald-700" onClick={() => void copyText(createdCodes.map((item) => item.code).join("\n"))}>
                  <Copy className="size-4" />
                  复制
                </Button>
              </div>
            </div>
          ) : null}
        </CardContent>
      </Card>

      <Card className="rounded-2xl border-white/80 bg-white/90 shadow-sm">
        <CardContent className="space-y-4 p-6">
          <h2 className="text-lg font-semibold tracking-tight">查验兑换码</h2>
          <div className="grid gap-3 md:grid-cols-[1fr_auto] md:items-end">
            <Input value={verifyInput} onChange={(event) => setVerifyInput(event.target.value)} placeholder="粘贴完整兑换码" className="h-10 rounded-xl border-stone-200 bg-white" />
            <Button variant="outline" className="h-10 rounded-xl border-stone-200 bg-white px-4 text-stone-700" onClick={() => void handleVerify()}>
              <Search className="size-4" />
              查验
            </Button>
          </div>
          {verifyResult ? <pre className="overflow-x-auto rounded-xl bg-stone-50 p-4 text-xs text-stone-700">{verifyResult}</pre> : null}
        </CardContent>
      </Card>

      <Card className="overflow-hidden rounded-2xl border-white/80 bg-white/90 shadow-sm">
        <CardContent className="p-0">
          <div className="overflow-x-auto">
            <Table className="min-w-[900px]">
              <TableHeader>
                <TableRow>
                  <TableHead>兑换码</TableHead>
                  <TableHead>额度</TableHead>
                  <TableHead>状态</TableHead>
                  <TableHead>创建时间</TableHead>
                  <TableHead>过期时间</TableHead>
                  <TableHead>兑换用户</TableHead>
                  <TableHead>兑换时间</TableHead>
                  <TableHead>操作</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {items.map((item) => (
                  <TableRow key={item.id} className="text-stone-600">
                    <TableCell>
                      <div className="font-medium text-stone-800">{item.display_code}</div>
                      <div className="font-mono text-xs text-stone-400">{item.id}</div>
                    </TableCell>
                    <TableCell>{item.image_quota}</TableCell>
                    <TableCell><StatusBadge status={item.status} /></TableCell>
                    <TableCell className="whitespace-nowrap text-xs">{formatDateTime(item.created_at)}</TableCell>
                    <TableCell className="whitespace-nowrap text-xs">{formatDateTime(item.expires_at)}</TableCell>
                    <TableCell>
                      <div>{item.redeemed_by_name || "—"}</div>
                      <div className="font-mono text-xs text-stone-400">{item.redeemed_by_id || ""}</div>
                    </TableCell>
                    <TableCell className="whitespace-nowrap text-xs">{formatDateTime(item.redeemed_at)}</TableCell>
                    <TableCell>
                      <Button variant="outline" className="h-8 rounded-lg border-stone-200 bg-white px-3 text-stone-700" disabled={pendingId === item.id} onClick={() => void handleToggle(item)}>
                        {pendingId === item.id ? <LoaderCircle className="size-4 animate-spin" /> : item.enabled ? "禁用" : "启用"}
                      </Button>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
          {!isLoading && items.length === 0 ? <div className="px-6 py-14 text-center text-sm text-stone-500">暂无兑换码</div> : null}
        </CardContent>
      </Card>
    </section>
  );
}

export default function RedeemCodesPage() {
  const { isCheckingAuth, session } = useAuthGuard(["admin"]);
  if (isCheckingAuth || !session || session.role !== "admin") {
    return <div className="flex min-h-[40vh] items-center justify-center"><LoaderCircle className="size-5 animate-spin text-stone-400" /></div>;
  }
  return <RedeemCodesContent />;
}
