(() => {
  const ENTRY_ATTR = "data-token2-image-entry";
  const IMAGE3_LOGIN_URL = "https://image3.mewinyou.shop/login";
  const TOKEN2_API_BASE = "/api/v1";
  const IMAGE_GROUP_ID = 12;
  const AUTO_KEY_NAME = "image3自动生成";
  const LABEL = "图片生成";
  const ICON =
    '<svg class="h-5 w-5 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.5" aria-hidden="true"><path stroke-linecap="round" stroke-linejoin="round" d="M2.25 15.75 7.5 10.5a2.25 2.25 0 0 1 3 0l3 3 1.5-1.5a2.25 2.25 0 0 1 3 0l3.75 3.75M3.75 19.5h16.5a1.5 1.5 0 0 0 1.5-1.5V6a1.5 1.5 0 0 0-1.5-1.5H3.75A1.5 1.5 0 0 0 2.25 6v12a1.5 1.5 0 0 0 1.5 1.5Zm11.25-9.75h.008v.008H15V9.75Z" /></svg>';

  function normalizePath(anchor) {
    try {
      return new URL(anchor.getAttribute("href") || "", window.location.origin).pathname.replace(/\/$/, "") || "/";
    } catch {
      return "";
    }
  }

  function isDashboard(anchor) {
    const path = normalizePath(anchor);
    return path === "/dashboard" || path === "/admin/dashboard";
  }

  function normalizedText(element) {
    return String(element?.textContent || "").replace(/\s+/g, " ").trim().toLowerCase();
  }

  function isBrandDashboardLink(anchor) {
    const siteName = normalizedText({ textContent: window.__APP_CONFIG__?.site_name || "" });
    const text = normalizedText(anchor);
    return Boolean(anchor.querySelector("img") || (siteName && text.includes(siteName)) || text.includes("tokenpush"));
  }

  function isLikelyMenuContainer(container, dashboardLink) {
    if (!container || container.tagName !== "NAV" || container.closest("header, [role='banner']")) return false;
    const anchors = Array.from(container.querySelectorAll("a[href]"));
    if (anchors.length < 2) return false;
    if (container.querySelector("[data-tour^='sidebar-'], [id^='sidebar-']")) return true;
    return anchors.some((anchor) => anchor !== dashboardLink && !isDashboard(anchor));
  }

  function findMenuContainer(dashboardLink) {
    const nav = dashboardLink.closest("nav");
    if (isLikelyMenuContainer(nav, dashboardLink)) return nav;
    return null;
  }

  function inactiveTemplate(nav, dashboardLink) {
    const anchors = Array.from(nav.querySelectorAll("a[href]"));
    return (
      anchors.find((anchor) => {
        if (anchor === dashboardLink || anchor.hasAttribute(ENTRY_ATTR)) return false;
        const className = String(anchor.getAttribute("class") || "");
        const ariaCurrent = String(anchor.getAttribute("aria-current") || "");
        return !className.includes("router-link-active") && !className.includes("router-link-exact-active") && ariaCurrent !== "page";
      }) || dashboardLink
    );
  }

  function replaceLabel(link, text = LABEL) {
    const textNodes = [];
    const walker = document.createTreeWalker(link, NodeFilter.SHOW_TEXT, {
      acceptNode(node) {
        return node.nodeValue && node.nodeValue.trim() ? NodeFilter.FILTER_ACCEPT : NodeFilter.FILTER_REJECT;
      },
    });
    while (walker.nextNode()) textNodes.push(walker.currentNode);
    if (textNodes.length) {
      textNodes[textNodes.length - 1].nodeValue = text;
      for (let i = 0; i < textNodes.length - 1; i += 1) textNodes[i].nodeValue = "";
    } else {
      link.textContent = text;
    }
  }

  function normalizeIconSize(link) {
    const svg = link.querySelector("svg");
    if (!svg) return;
    svg.outerHTML = ICON;
  }

  async function token2Fetch(path, options = {}) {
    const authToken = localStorage.getItem("auth_token");
    if (!authToken) {
      throw new Error("请先登录 token2 后再打开图片生成");
    }

    const response = await fetch(`${TOKEN2_API_BASE}${path}`, {
      ...options,
      credentials: "include",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${authToken}`,
        ...(options.headers || {}),
      },
    });
    const payload = await response.json().catch(() => null);
    if (!response.ok) {
      throw new Error(payload?.message || payload?.detail || `请求失败 (${response.status})`);
    }
    if (payload && typeof payload === "object" && "code" in payload) {
      if (payload.code === 0) return payload.data;
      throw new Error(payload.message || "请求失败");
    }
    return payload;
  }

  function pageItems(data) {
    if (Array.isArray(data)) return data;
    if (Array.isArray(data?.items)) return data.items;
    if (Array.isArray(data?.data)) return data.data;
    return [];
  }

  function pageCount(data, pageSize) {
    const explicitPages = Number(data?.pages || data?.total_pages || data?.pagination?.pages || data?.pagination?.total_pages || 0);
    if (explicitPages > 0) return explicitPages;
    const total = Number(data?.total || data?.pagination?.total || 0);
    if (total > 0) return Math.ceil(total / pageSize);
    return 1;
  }

  function isImage2Key(item) {
    const groupId = Number(item?.group_id || item?.group?.id || 0);
    const status = String(item?.status || "active").toLowerCase();
    return groupId === IMAGE_GROUP_ID && status === "active" && typeof item?.key === "string" && item.key.trim();
  }

  async function listFirstImage2Key() {
    const pageSize = 100;
    for (let page = 1; page <= 10; page += 1) {
      const params = new URLSearchParams({
        page: String(page),
        page_size: String(pageSize),
        sort_by: "created_at",
        sort_order: "desc",
      });
      const data = await token2Fetch(`/keys?${params.toString()}`);
      const found = pageItems(data).find(isImage2Key);
      if (found) return found;
      if (page >= pageCount(data, pageSize)) break;
    }
    return null;
  }

  async function createImage2Key() {
    const created = await token2Fetch("/keys", {
      method: "POST",
      body: JSON.stringify({
        name: AUTO_KEY_NAME,
        group_id: IMAGE_GROUP_ID,
      }),
    });
    if (isImage2Key(created)) return created;
    return listFirstImage2Key();
  }

  async function resolveImage2Key() {
    return (await listFirstImage2Key()) || (await createImage2Key());
  }

  function image3LoginUrl(apiKey) {
    return `${IMAGE3_LOGIN_URL}#apiKey=${encodeURIComponent(apiKey)}`;
  }

  function openPendingTab() {
    const targetWindow = window.open("about:blank", "_blank");
    if (!targetWindow) return null;
    try {
      targetWindow.opener = null;
      targetWindow.document.title = "正在进入图片生成";
      targetWindow.document.body.style.cssText =
        "margin:0;min-height:100vh;display:grid;place-items:center;font:14px -apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;color:#444;background:#f7f3ee";
      targetWindow.document.body.textContent = "正在进入图片生成...";
    } catch {
      // Some browsers restrict writes to the new tab; location assignment below
      // still works for the window handle.
    }
    return targetWindow;
  }

  function navigateToImage3(targetWindow, apiKey) {
    const url = image3LoginUrl(apiKey);
    if (targetWindow && !targetWindow.closed) {
      targetWindow.location.href = url;
      return;
    }
    window.location.href = url;
  }

  async function openImage3(link) {
    if (link.dataset.loading === "1") return;
    const originalText = link.textContent || LABEL;
    const targetWindow = openPendingTab();
    link.dataset.loading = "1";
    link.setAttribute("aria-busy", "true");
    replaceLabel(link, "正在进入");
    try {
      const key = await resolveImage2Key();
      if (!key?.key) {
        throw new Error("没有可用的 image2 密钥");
      }
      navigateToImage3(targetWindow, key.key);
    } catch (error) {
      if (targetWindow && !targetWindow.closed) {
        targetWindow.close();
      }
      link.dataset.loading = "0";
      link.removeAttribute("aria-busy");
      replaceLabel(link, originalText.trim() || LABEL);
      alert(error instanceof Error ? error.message : "打开图片生成失败");
    }
  }

  function buildEntry(nav, dashboardLink) {
    const template = inactiveTemplate(nav, dashboardLink);
    const link = template.cloneNode(true);
    link.setAttribute(ENTRY_ATTR, "1");
    link.setAttribute("data-tour", "sidebar-image-generation");
    link.setAttribute("href", IMAGE3_LOGIN_URL);
    link.removeAttribute("id");
    link.removeAttribute("aria-current");
    link.classList.remove("router-link-active", "router-link-exact-active");
    normalizeIconSize(link);
    replaceLabel(link);
    link.addEventListener("click", (event) => {
      event.preventDefault();
      void openImage3(link);
    });
    return link;
  }

  function inject() {
    const dashboards = Array.from(document.querySelectorAll("a[href]")).filter((anchor) => isDashboard(anchor) && !isBrandDashboardLink(anchor));
    for (const dashboardLink of dashboards) {
      const nav = findMenuContainer(dashboardLink);
      if (!nav || nav.querySelector(`[${ENTRY_ATTR}]`)) continue;
      dashboardLink.insertAdjacentElement("afterend", buildEntry(nav, dashboardLink));
    }
  }

  let timer = 0;
  function schedule() {
    clearTimeout(timer);
    timer = setTimeout(inject, 80);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", inject, { once: true });
  } else {
    inject();
  }
  new MutationObserver(schedule).observe(document.documentElement, { childList: true, subtree: true });
})();
