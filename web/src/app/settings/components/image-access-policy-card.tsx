"use client";

import { LoaderCircle, Save, ShieldCheck } from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Textarea } from "@/components/ui/textarea";

import { useSettingsStore } from "../store";

function idListText(value: unknown): string {
  return Array.isArray(value) ? value.join("\n") : "";
}

function parseIdList(value: string): number[] {
  const ids: number[] = [];
  for (const item of value.split(/[,\s]+/)) {
    const id = Number(item.trim());
    if (Number.isInteger(id) && id > 0 && !ids.includes(id)) {
      ids.push(id);
    }
  }
  return ids;
}

export function ImageAccessPolicyCard() {
  const [userIdsText, setUserIdsText] = useState("");
  const [keyIdsText, setKeyIdsText] = useState("");
  const config = useSettingsStore((state) => state.config);
  const isLoadingConfig = useSettingsStore((state) => state.isLoadingConfig);
  const isSavingConfig = useSettingsStore((state) => state.isSavingConfig);
  const saveConfig = useSettingsStore((state) => state.saveConfig);
  const storeSetUserIdsText = useSettingsStore((state) => state.setImage1kOnlySub2APIUserIdsText);
  const storeSetKeyIdsText = useSettingsStore((state) => state.setImage1kOnlySub2APIKeyIdsText);

  const userIds = Array.isArray(config?.image_1k_only_sub2api_user_ids) ? config.image_1k_only_sub2api_user_ids : [];
  const keyIds = Array.isArray(config?.image_1k_only_sub2api_key_ids) ? config.image_1k_only_sub2api_key_ids : [];
  const parsedUserIds = useMemo(() => parseIdList(userIdsText), [userIdsText]);
  const parsedKeyIds = useMemo(() => parseIdList(keyIdsText), [keyIdsText]);

  useEffect(() => {
    if (isLoadingConfig) {
      return;
    }
    setUserIdsText(idListText(userIds));
    setKeyIdsText(idListText(keyIds));
  }, [isLoadingConfig, keyIds.join(","), userIds.join(",")]);

  const handleSave = async () => {
    storeSetUserIdsText(userIdsText);
    storeSetKeyIdsText(keyIdsText);
    await saveConfig();
  };

  if (isLoadingConfig) {
    return (
      <Card className="rounded-2xl border-white/80 bg-white/90 shadow-sm">
        <CardContent className="flex items-center justify-center p-10">
          <LoaderCircle className="size-5 animate-spin text-stone-400" />
        </CardContent>
      </Card>
    );
  }

  return (
    <Card className="rounded-2xl border-white/80 bg-white/90 shadow-sm">
      <CardContent className="space-y-5 p-6">
        <div className="flex flex-col gap-3 border-b border-stone-100 pb-5 md:flex-row md:items-center md:justify-between">
          <div className="space-y-1">
            <div className="flex items-center gap-2">
              <ShieldCheck className="size-5 text-stone-700" />
              <h2 className="text-lg font-semibold text-stone-950">图片 1K 限制</h2>
            </div>
            <p className="text-sm leading-6 text-stone-500">受限对象提交更大尺寸时会等比缩放到最大边 1024 后继续生成。</p>
          </div>
          <div className="flex flex-wrap gap-2">
            <Badge variant="info">用户 {parsedUserIds.length}</Badge>
            <Badge variant="warning">密钥 {parsedKeyIds.length}</Badge>
          </div>
        </div>

        <div className="grid gap-5 lg:grid-cols-2">
          <div className="space-y-2">
            <label className="text-sm font-medium text-stone-700">Token2 用户 ID</label>
            <Textarea
              value={userIdsText}
              onChange={(event) => setUserIdsText(event.target.value)}
              placeholder={"39\n42\n88"}
              className="min-h-44 rounded-xl border-stone-200 bg-white font-mono text-sm shadow-none"
            />
            <p className="text-xs leading-5 text-stone-500">限制用户下所有 image3 key。支持换行、逗号或空格分隔。</p>
          </div>

          <div className="space-y-2">
            <label className="text-sm font-medium text-stone-700">Token2 Key ID</label>
            <Textarea
              value={keyIdsText}
              onChange={(event) => setKeyIdsText(event.target.value)}
              placeholder={"93\n104"}
              className="min-h-44 rounded-xl border-stone-200 bg-white font-mono text-sm shadow-none"
            />
            <p className="text-xs leading-5 text-stone-500">只限制指定 key，不影响同一用户的其他 key。</p>
          </div>
        </div>

        <div className="rounded-xl border border-stone-200 bg-stone-50 px-4 py-3 text-sm leading-6 text-stone-600">
          示例：2048x2048 会变为 1024x1024，3840x2160 会变为 1024x576；留空或 auto 保持 1K 档。
        </div>

        <div className="flex justify-end">
          <Button
            className="h-10 rounded-xl bg-stone-950 px-5 text-white hover:bg-stone-800"
            onClick={() => void handleSave()}
            disabled={isSavingConfig}
          >
            {isSavingConfig ? <LoaderCircle className="size-4 animate-spin" /> : <Save className="size-4" />}
            保存限制
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}
