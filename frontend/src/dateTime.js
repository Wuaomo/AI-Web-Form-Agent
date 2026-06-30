const chinaTimeFormatter = new Intl.DateTimeFormat("zh-CN", {
  timeZone: "Asia/Shanghai",
  year: "numeric",
  month: "2-digit",
  day: "2-digit",
  hour: "2-digit",
  minute: "2-digit",
  hour12: false,
});

function normalizeBackendTimestamp(value) {
  if (!value || typeof value !== "string") {
    return value;
  }

  const normalized = value.trim().replace(" ", "T");
  if (/[zZ]|[+-]\d{2}:?\d{2}$/.test(normalized)) {
    return normalized;
  }
  return `${normalized}Z`;
}

export function formatChinaTime(value) {
  const date = new Date(normalizeBackendTimestamp(value));
  if (Number.isNaN(date.getTime())) {
    return "—";
  }
  return chinaTimeFormatter.format(date);
}
