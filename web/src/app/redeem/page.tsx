"use client";

import { useEffect, useState } from "react";
import { LoaderCircle, TicketCheck } from "lucide-react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { fetchAuthProfile, redeemCode, type LoginResponse } from "@/lib/api";
import { useAuthGuard } from "@/lib/use-auth-guard";

function RedeemContent() {
  const { session } = useAuthGuard(["user"]);
  const [code, setCode] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [profile, setProfile] = useState<LoginResponse | null>(null);

  const currentName = profile?.name || session?.name || "普通用户";
  const imageQuota = profile?.image_quota ?? 0;
  const imageUsed = profile?.image_used ?? 0;
  const imageRemaining = profile?.image_remaining ?? null;


  useEffect(() => {
    let active = true;
    const loadProfile = async () => {
      try {
        const data = await fetchAuthProfile();
        if (active) {
          setProfile(data);
        }
      } catch {
        // keep the validated auth session fallback
      }
    };
    void loadProfile();
    return () => {
      active = false;
    };
  }, []);

  const handleRedeem = async () => {
    const trimmedCode = code.trim();
    if (!trimmedCode) {
      toast.error("请输入兑换码");
      return;
    }
    setIsSubmitting(true);
    try {
      const data = await redeemCode(trimmedCode);
      setProfile({
        ok: true,
        version: "",
        role: "user",
        subject_id: data.profile.subject_id,
        name: String(data.profile.name || session?.name || "普通用户"),
        image_quota: data.profile.image_quota,
        image_used: data.profile.image_used,
        image_remaining: data.profile.image_remaining,
      });
      setCode("");
      toast.success(`兑换成功，已增加 ${data.image_quota_added} 张图片额度`);
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "兑换失败");
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <section className="mx-auto grid w-full max-w-[980px] gap-5 lg:grid-cols-[minmax(0,1.2fr)_minmax(280px,.8fr)]">
      <Card className="rounded-2xl border-white/80 bg-white/90 shadow-sm">
        <CardContent className="space-y-5 p-6">
          <div className="space-y-1">
            <div className="text-xs font-semibold tracking-[0.18em] text-stone-500 uppercase">Redeem</div>
            <h1 className="text-2xl font-semibold tracking-tight">兑换图片额度</h1>
            <p className="text-sm text-stone-500">输入管理员发放的一次性兑换码，成功后会增加当前账号的图片额度。</p>
          </div>
          <div className="space-y-2">
            <label className="text-sm font-medium text-stone-700">兑换码</label>
            <Input
              value={code}
              onChange={(event) => setCode(event.target.value)}
              onKeyDown={(event) => event.key === "Enter" && void handleRedeem()}
              placeholder="RC-XXXX-XXXX-XXXX-XXXX"
              className="h-12 rounded-2xl border-stone-200 bg-white px-4 font-mono"
            />
          </div>
          <Button onClick={() => void handleRedeem()} disabled={isSubmitting} className="h-11 rounded-2xl bg-stone-950 px-5 text-white hover:bg-stone-800">
            {isSubmitting ? <LoaderCircle className="size-4 animate-spin" /> : <TicketCheck className="size-4" />}
            立即兑换
          </Button>
          <div className="rounded-2xl bg-stone-50 px-4 py-3 text-sm leading-7 text-stone-600">
            当前用户：{currentName}<br />
            总额度：{imageQuota > 0 ? imageQuota : "不限"}<br />
            已用：{imageUsed}<br />
            剩余：{imageRemaining ?? "不限"}
          </div>
        </CardContent>
      </Card>
      <Card className="rounded-2xl border-white/80 bg-white/90 shadow-sm">
        <CardContent className="space-y-3 p-6 text-sm leading-7 text-stone-500">
          <h2 className="text-lg font-semibold tracking-tight text-stone-900">说明</h2>
          <ul className="list-disc space-y-1 pl-5">
            <li>每个兑换码只能成功兑换一次。</li>
            <li>兑换码可能设置过期时间，请在有效期内使用。</li>
            <li>兑换成功后如果画图页面额度未刷新，请刷新页面。</li>
          </ul>
        </CardContent>
      </Card>
    </section>
  );
}

export default function RedeemPage() {
  const { isCheckingAuth, session } = useAuthGuard(["user"]);
  if (isCheckingAuth || !session || session.role !== "user") {
    return <div className="flex min-h-[40vh] items-center justify-center"><LoaderCircle className="size-5 animate-spin text-stone-400" /></div>;
  }
  return <RedeemContent />;
}
