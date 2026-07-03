"use client";

import { useEffect, useMemo, useState } from "react";
import { ChevronLeft, ChevronRight, Eye, LoaderCircle, RefreshCw, Search, WalletCards } from "lucide-react";
import { toast } from "sonner";

import { DateRangeFilter } from "@/components/date-range-filter";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { fetchImageBillingLogs, type ImageBillingLog } from "@/lib/api";
import { useAuthGuard } from "@/lib/use-auth-guard";

const actionLabels: Record<string, string> = {
  debit: "扣费",
  refund: "退款",
};

const statusLabels: Record<string, string> = {
  success: "成功",
  failed: "失败",
};

const modeLabels: Record<string, string> = {
  generate: "文生图",
  edit: "改图",
};

function amountValue(value: string) {
  const parsed = Number(value || 0);
  return Number.isFinite(parsed) ? parsed : 0;
}

function formatAmount(value: string | number) {
  const parsed = typeof value === "number" ? value : amountValue(value);
  return parsed.toFixed(8).replace(/\.?0+$/, "") || "0";
}

function formatTime(value: string) {
  return value.replace("T", " ").replace(/\.\d+/, "");
}

function actionVariant(action: string, status: string): "success" | "danger" | "warning" | "info" | "secondary" {
  if (status === "failed") return "danger";
  if (action === "refund") return "info";
  if (action === "debit") return "success";
  return "secondary";
}

function BillingContent() {
  const [items, setItems] = useState<ImageBillingLog[]>([]);
  const [userEmail, setUserEmail] = useState("");
  const [action, setAction] = useState("all");
  const [status, setStatus] = useState("all");
  const [startDate, setStartDate] = useState("");
  const [endDate, setEndDate] = useState("");
  const [limit, setLimit] = useState("200");
  const [page, setPage] = useState(1);
  const [isLoading, setIsLoading] = useState(true);
  const [detailLog, setDetailLog] = useState<ImageBillingLog | null>(null);

  const pageSize = 15;
  const pageCount = Math.max(1, Math.ceil(items.length / pageSize));
  const safePage = Math.min(page, pageCount);
  const currentRows = items.slice((safePage - 1) * pageSize, safePage * pageSize);

  const totals = useMemo(() => {
    let debits = 0;
    let refunds = 0;
    let failed = 0;
    for (const item of items) {
      if (item.status === "failed") {
        failed += 1;
        continue;
      }
      if (item.action === "debit") debits += amountValue(item.amount);
      if (item.action === "refund") refunds += amountValue(item.amount);
    }
    return { debits, refunds, net: debits - refunds, failed };
  }, [items]);

  const loadLogs = async () => {
    setIsLoading(true);
    try {
      const data = await fetchImageBillingLogs({
        user_email: userEmail.trim(),
        action: action === "all" ? "" : action,
        status: status === "all" ? "" : status,
        start_date: startDate,
        end_date: endDate,
        limit: Math.max(1, Math.min(Number(limit) || 200, 1000)),
      });
      setItems(data.items);
      setPage(1);
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "加载扣费记录失败");
    } finally {
      setIsLoading(false);
    }
  };

  const clearFilters = () => {
    setUserEmail("");
    setAction("all");
    setStatus("all");
    setStartDate("");
    setEndDate("");
    setLimit("200");
  };

  useEffect(() => {
    void loadLogs();
  }, []);

  return (
    <section className="space-y-5">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
        <div className="space-y-1">
          <div className="text-xs font-semibold tracking-[0.18em] text-stone-500 uppercase">Billing</div>
          <h1 className="text-2xl font-semibold tracking-tight">图片扣费记录</h1>
        </div>
        <div className="flex flex-wrap gap-2">
          <Input
            value={userEmail}
            onChange={(event) => setUserEmail(event.target.value)}
            placeholder="用户邮箱"
            className="h-10 w-[220px] rounded-xl border-stone-200"
          />
          <Select value={action} onValueChange={setAction}>
            <SelectTrigger className="h-10 w-[120px] rounded-xl border-stone-200 bg-white"><SelectValue /></SelectTrigger>
            <SelectContent>
              <SelectItem value="all">全部动作</SelectItem>
              <SelectItem value="debit">扣费</SelectItem>
              <SelectItem value="refund">退款</SelectItem>
            </SelectContent>
          </Select>
          <Select value={status} onValueChange={setStatus}>
            <SelectTrigger className="h-10 w-[120px] rounded-xl border-stone-200 bg-white"><SelectValue /></SelectTrigger>
            <SelectContent>
              <SelectItem value="all">全部状态</SelectItem>
              <SelectItem value="success">成功</SelectItem>
              <SelectItem value="failed">失败</SelectItem>
            </SelectContent>
          </Select>
          <DateRangeFilter startDate={startDate} endDate={endDate} onChange={(start, end) => { setStartDate(start); setEndDate(end); }} />
          <Input
            value={limit}
            onChange={(event) => setLimit(event.target.value.replace(/\D/g, ""))}
            placeholder="条数"
            className="h-10 w-[86px] rounded-xl border-stone-200"
          />
          <Button variant="outline" onClick={clearFilters} className="h-10 rounded-xl border-stone-200 bg-white px-4 text-stone-700">
            清除
          </Button>
          <Button onClick={() => void loadLogs()} disabled={isLoading} className="h-10 rounded-xl bg-stone-950 px-4 text-white hover:bg-stone-800">
            {isLoading ? <LoaderCircle className="size-4 animate-spin" /> : <Search className="size-4" />}
            查询
          </Button>
        </div>
      </div>

      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <div className="rounded-xl border border-stone-200 bg-white/85 p-4">
          <div className="flex items-center gap-2 text-xs text-stone-500"><WalletCards className="size-4" />成功扣费</div>
          <div className="mt-2 text-xl font-semibold text-stone-950">{formatAmount(totals.debits)}</div>
        </div>
        <div className="rounded-xl border border-stone-200 bg-white/85 p-4">
          <div className="text-xs text-stone-500">成功退款</div>
          <div className="mt-2 text-xl font-semibold text-sky-700">{formatAmount(totals.refunds)}</div>
        </div>
        <div className="rounded-xl border border-stone-200 bg-white/85 p-4">
          <div className="text-xs text-stone-500">净扣费</div>
          <div className="mt-2 text-xl font-semibold text-emerald-700">{formatAmount(totals.net)}</div>
        </div>
        <div className="rounded-xl border border-stone-200 bg-white/85 p-4">
          <div className="text-xs text-stone-500">失败拦截</div>
          <div className="mt-2 text-xl font-semibold text-rose-700">{totals.failed}</div>
        </div>
      </div>

      <Card className="overflow-hidden rounded-2xl border-white/80 bg-white/90 shadow-sm">
        <CardContent className="p-0">
          <div className="flex flex-wrap items-center justify-between gap-3 border-b border-stone-100 px-5 py-4">
            <div className="text-sm text-stone-600">共 {items.length} 条</div>
            <Button variant="ghost" className="h-8 rounded-lg px-3 text-stone-500" onClick={() => void loadLogs()} disabled={isLoading}>
              <RefreshCw className={`size-4 ${isLoading ? "animate-spin" : ""}`} />
              刷新
            </Button>
          </div>
          <div className="overflow-x-auto">
            <Table className="min-w-[1180px]">
              <TableHeader>
                <TableRow>
                  <TableHead>时间</TableHead>
                  <TableHead>用户</TableHead>
                  <TableHead>Key</TableHead>
                  <TableHead>动作</TableHead>
                  <TableHead>金额</TableHead>
                  <TableHead>扣前余额</TableHead>
                  <TableHead>扣后余额</TableHead>
                  <TableHead>类型</TableHead>
                  <TableHead>模型</TableHead>
                  <TableHead>提示词/错误</TableHead>
                  <TableHead className="w-24">操作</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {currentRows.map((item) => (
                  <TableRow key={String(item.id)} className="text-stone-600">
                    <TableCell className="whitespace-nowrap">{formatTime(item.created_at)}</TableCell>
                    <TableCell>
                      <div className="max-w-[220px] truncate text-stone-700">{item.user_email || "-"}</div>
                      <div className="text-xs text-stone-400">user {item.user_id}</div>
                    </TableCell>
                    <TableCell>
                      <div className="font-mono text-xs text-stone-600">{item.api_key}</div>
                      <div className="text-xs text-stone-400">id {item.api_key_id}</div>
                    </TableCell>
                    <TableCell>
                      <Badge variant={actionVariant(item.action, item.status)} className="rounded-md">
                        {actionLabels[item.action] || item.action || "-"} · {statusLabels[item.status] || item.status || "-"}
                      </Badge>
                    </TableCell>
                    <TableCell className="font-medium text-stone-900">{formatAmount(item.amount)}</TableCell>
                    <TableCell>{formatAmount(item.balance_before)}</TableCell>
                    <TableCell>{formatAmount(item.balance_after)}</TableCell>
                    <TableCell>{modeLabels[item.mode] || item.mode || "-"}</TableCell>
                    <TableCell className="max-w-[160px] truncate">{item.model || "-"}</TableCell>
                    <TableCell className="max-w-[320px] truncate text-stone-500">{item.error || item.prompt_preview || "-"}</TableCell>
                    <TableCell>
                      <Button variant="ghost" className="h-8 rounded-lg px-3 text-stone-600" onClick={() => setDetailLog(item)}>
                        <Eye className="size-4" />
                        详情
                      </Button>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
          <div className="flex items-center justify-end gap-2 border-t border-stone-100 px-4 py-3 text-sm text-stone-500">
            <span>第 {safePage} / {pageCount} 页，共 {items.length} 条</span>
            <Button variant="outline" size="icon" className="size-9 rounded-lg border-stone-200 bg-white" disabled={safePage <= 1} onClick={() => setPage((value) => Math.max(1, value - 1))}>
              <ChevronLeft className="size-4" />
            </Button>
            <Button variant="outline" size="icon" className="size-9 rounded-lg border-stone-200 bg-white" disabled={safePage >= pageCount} onClick={() => setPage((value) => Math.min(pageCount, value + 1))}>
              <ChevronRight className="size-4" />
            </Button>
          </div>
          {!isLoading && items.length === 0 ? <div className="px-6 py-14 text-center text-sm text-stone-500">没有找到扣费记录</div> : null}
        </CardContent>
      </Card>

      <Dialog open={Boolean(detailLog)} onOpenChange={(open) => { if (!open) setDetailLog(null); }}>
        <DialogContent className="w-[min(92vw,760px)] rounded-2xl">
          <DialogHeader>
            <DialogTitle>扣费详情</DialogTitle>
          </DialogHeader>
          <div className="grid gap-3 rounded-xl border border-stone-200 bg-white p-4 text-sm text-stone-600 md:grid-cols-2">
            {detailLog ? Object.entries(detailLog).map(([key, value]) => (
              <div key={key} className="flex items-start justify-between gap-4">
                <span className="shrink-0 text-stone-400">{key}</span>
                <span className="text-right font-medium break-all text-stone-700">{String(value || "-")}</span>
              </div>
            )) : null}
          </div>
        </DialogContent>
      </Dialog>
    </section>
  );
}

export default function BillingPage() {
  const { isCheckingAuth, session } = useAuthGuard(["admin"]);
  if (isCheckingAuth || !session || session.role !== "admin") {
    return <div className="flex min-h-[40vh] items-center justify-center"><LoaderCircle className="size-5 animate-spin text-stone-400" /></div>;
  }
  return <BillingContent />;
}
