const UTC8_TIME_ZONE = "Asia/Shanghai";

type DateTimeFormatOptions = {
  seconds?: boolean;
  date?: boolean;
  time?: boolean;
};

function parseDateTime(value?: string | number | Date | null) {
  if (value == null || value === "") {
    return null;
  }
  if (value instanceof Date) {
    return Number.isNaN(value.getTime()) ? null : value;
  }
  if (typeof value === "number") {
    const date = new Date(value);
    return Number.isNaN(date.getTime()) ? null : date;
  }

  const text = String(value).trim();
  if (!text) {
    return null;
  }

  const hasTimezone = /(?:Z|[+-]\d{2}:?\d{2})$/i.test(text);
  const normalized = text.includes("T") ? text : text.replace(" ", "T");
  const date = new Date(hasTimezone ? normalized : `${normalized}+00:00`);
  return Number.isNaN(date.getTime()) ? null : date;
}

function utc8Parts(date: Date) {
  const parts = new Intl.DateTimeFormat("en-CA", {
    timeZone: UTC8_TIME_ZONE,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hour12: false,
  }).formatToParts(date);
  return Object.fromEntries(parts.map((part) => [part.type, part.value]));
}

export function formatUtc8DateTime(value?: string | number | Date | null, options: DateTimeFormatOptions = {}) {
  const date = parseDateTime(value);
  if (!date) {
    return value ? String(value) : "—";
  }

  const { date: includeDate = true, time: includeTime = true, seconds = true } = options;
  const parts = utc8Parts(date);
  const dateText = `${parts.year}-${parts.month}-${parts.day}`;
  const timeText = seconds ? `${parts.hour}:${parts.minute}:${parts.second}` : `${parts.hour}:${parts.minute}`;

  if (includeDate && includeTime) {
    return `${dateText} ${timeText}`;
  }
  if (includeDate) {
    return dateText;
  }
  return timeText;
}

export function formatUtc8MonthDayTime(value?: string | number | Date | null) {
  const date = parseDateTime(value);
  if (!date) {
    return value ? String(value) : "—";
  }
  const parts = utc8Parts(date);
  return `${parts.month}-${parts.day} ${parts.hour}:${parts.minute}`;
}

export function getDateTimeMs(value?: string | number | Date | null) {
  return parseDateTime(value)?.getTime() ?? NaN;
}
