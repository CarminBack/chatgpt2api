"use client";

import { useMemo, useState } from "react";

import webConfig from "@/constants/common-env";
import type { ReleaseInfo } from "@/lib/release";

function readLocalReleases(): ReleaseInfo[] {
  return JSON.parse(process.env.NEXT_PUBLIC_APP_RELEASES || "[]");
}

export function useVersionCheck() {
  const currentVersion = webConfig.appVersion;
  const localReleases = useMemo(readLocalReleases, []);
  const [latestVersion, setLatestVersion] = useState(currentVersion);
  const [releases, setReleases] = useState<ReleaseInfo[]>(localReleases);
  const [open, setOpen] = useState(false);

  const openReleaseModal = () => {
    setLatestVersion(currentVersion);
    setReleases(localReleases);
    setOpen(true);
  };

  return {
    open,
    setOpen,
    openReleaseModal,
    latestVersion,
    releases,
    hasNewVersion: false,
  };
}
