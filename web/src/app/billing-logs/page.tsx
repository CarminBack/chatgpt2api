"use client";

import { useEffect, useState } from "react";
import { ChevronLeft, ChevronRight, LoaderCircle, RefreshCw, Search } from "lucide-react";
import { toast } from "sonner";

import { DateRangeFilter } from "@/components/date-range-filter";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { fetchImageBillingLogs, type ImageBillingLog } from "@/lib/api";
import { useAuthGuard } from "@/lib/use-auth-guard";

function formatDate(str: string) {
  if (!str) return "-";
  try {
    return new Date(str).toLocaleString("zh-CN", { hour12: false });
  } catch {
    return str;
  }
}

function formatAmount(val: string) {
  const n = parseFloat(val);
  if (isNaN(n)) return val || "-";
  return `¥${n.toFixed(4)}`;
}

function ActionBadge({ action }: { action: string }) {
  if (action === "debit") return <Badge variant="danger" className="rounded-md">扣费</Badge>;
  if (action === "refund") return <Badge variant="success" className="rounded-md">退款</Badge>;
  return <Badge variant="secondary" className="rounded-md">{action}</Badge>;
}

function StatusBadge({ status }: { status: string }) {
  if (status === "success") return <Badge variant="success" className="rounded-md">成功</Badge>;
  if (status === "failed") return <Badge variant="danger" className="rounded-md">失败</Badge>;
  return <Badge variant="secondary" className="rounded-md">{status}</Badge>;
}

function BillingLogsContent() {
  const [items, setItems] = useState<ImageBillingLog[]>([]);
  const [userEmail, setUserEmail] = useState("");
  const [action, setAction] = useState("all");
  const [status, setStatus] = useState("all");
  const [startDate, setStartDate] = useState("");
  const [endDate, setEndDate] = useState("");
  const [page, setPage] = useState(1);
  const [isLoading, setIsLoading] = useState(true);

  const pageSize = 20;
  const pageCount = Math.max(1, Math.ceil(items.length / pageSize));
  const safePage = Math.min(page, pageCount);
  const currentRows = items.slice((safePage - 1) * pageSize, safePage * pageSize);

  const loadLogs = async () => {
    setIsLoading(true);
    try {
      const data = await fetchImageBillingLogs({
        user_email: userEmail.trim(),
        action: action === "all" ? "" : action,
        status: status === "all" ? "" : status,
        start_date: startDate,
        end_date: endDate,
        limit: 500,
      });
      setItems(data.items);
      setPage(1);
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "加载扣费流水失败");
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
  };

  useEffect(() => {
    void loadLogs();
  }, [startDate, endDate]);

  return (
    <section className="space-y-5">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
        <div className="space-y-1">
          <div className="text-xs font-semibold tracking-[0.18em] text-stone-500 uppercase">Billing</div>
          <h1 className="text-2xl font-semibold tracking-tight">生图扣费流水</h1>
        </div>
        <div className="flex flex-wrap gap-2">
          <Input
            placeholder="用户邮箱"
            value={userEmail}
            onChange={(e) => setUserEmail(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && void loadLogs()}
            className="h-10 w-[180px] rounded-xl border-stone-200 bg-white"
          />
          <Select value={action} onValueChange={setAction}>
            <SelectTrigger className="h-10 w-[120px] rounded-xl border-stone-200 bg-white"><SelectValue /></SelectTrigger>
            <SelectContent>
              <SelectItem value="all">全部操作</SelectItem>
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
          <Button variant="outline" onClick={clearFilters} className="h-10 rounded-xl border-stone-200 bg-white px-4 text-stone-700">
            清除筛选
          </Button>
          <Button onClick={() => void loadLogs()} disabled={isLoading} className="h-10 rounded-xl bg-stone-950 px-4 text-white hover:bg-stone-800">
            {isLoading ? <LoaderCircle className="size-4 animate-spin" /> : <Search className="size-4" />}
            查询
          </Button>
        </div>
      </div>

      <Card className="overflow-hidden rounded-2xl border-white/80 bg-white/90 shadow-sm">
        <CardContent className="p-0">
          <div className="flex items-center justify-between gap-3 border-b border-stone-100 px-5 py-4">
            <span className="text-sm text-stone-600">共 {items.length} 条</span>
            <Button variant="ghost" className="h-8 rounded-lg px-3 text-stone-500" onClick={() => void loadLogs()} disabled={isLoading}>
              <RefreshCw className={`size-4 ${isLoading ? "animate-spin" : ""}`} />
              刷新
            </Button>
          </div>
          <div className="overflow-x-auto">
            <Table className="min-w-[900px]">
              <TableHeader>
                <TableRow>
                  <TableHead>时间</TableHead>
                  <TableHead>操作</TableHead>
                  <TableHead>状态</TableHead>
                  <TableHead>用户邮箱</TableHead>
                  <TableHead>金额</TableHead>
                  <TableHead>扣前余额</TableHead>
                  <TableHead>扣后余额</TableHead>
                  <TableHead>模型</TableHead>
                  <TableHead>模式</TableHead>
                  <TableHead>Prompt 摘要</TableHead>
                  <TableHead>错误信息</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {currentRows.map((item) => (
                  <TableRow key={item.id} className="text-stone-600">
                    <TableCell className="whitespace-nowrap text-xs">{formatDate(item.created_at)}</TableCell>
                    <TableCell><ActionBadge action={item.action} /></TableCell>
                    <TableCell><StatusBadge status={item.status} /></TableCell>
                    <TableCell className="max-w-[180px] truncate text-sm">{item.user_email || "-"}</TableCell>
                    <TableCell className="whitespace-nowrap font-mono text-sm">{formatAmount(item.amount)}</TableCell>
                    <TableCell className="whitespace-nowrap font-mono text-sm">{formatAmount(item.balance_before)}</TableCell>
                    <TableCell className="whitespace-nowrap font-mono text-sm">{formatAmount(item.balance_after)}</TableCell>
                    <TableCell className="text-xs">{item.model || "-"}</TableCell>
                    <TableCell className="text-xs">{item.mode || "-"}</TableCell>
                    <TableCell className="max-w-[200px] truncate text-xs text-stone-500" title={item.prompt_preview}>{item.prompt_preview || "-"}</TableCell>
                    <TableCell className="max-w-[180px] truncate text-xs text-rose-500" title={item.error}>{item.error || "-"}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
          <div className="flex items-center justify-end gap-2 border-t border-stone-100 px-4 py-3 text-sm text-stone-500">
            <span>第 {safePage} / {pageCount} 页，共 {items.length} 条</span>
            <Button variant="outline" size="icon" className="size-9 rounded-lg border-stone-200 bg-white" disabled={safePage <= 1} onClick={() => setPage((v) => Math.max(1, v - 1))}>
              <ChevronLeft className="size-4" />
            </Button>
            <Button variant="outline" size="icon" className="size-9 rounded-lg border-stone-200 bg-white" disabled={safePage >= pageCount} onClick={() => setPage((v) => Math.min(pageCount, v + 1))}>
              <ChevronRight className="size-4" />
            </Button>
          </div>
          {!isLoading && items.length === 0 ? <div className="px-6 py-14 text-center text-sm text-stone-500">没有找到扣费流水记录</div> : null}
        </CardContent>
      </Card>
    </section>
  );
}

export default function BillingLogsPage() {
  const { isCheckingAuth, session } = useAuthGuard(["admin"]);
  if (isCheckingAuth || !session || session.role !== "admin") {
    return <div className="flex min-h-[40vh] items-center justify-center"><LoaderCircle className="size-5 animate-spin text-stone-400" /></div>;
  }
  return <BillingLogsContent />;
}
