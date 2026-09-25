export const TYPE_LABEL = {
  TAX_INVOICE: "Tax Invoice",
  BILL_OF_SUPPLY: "Bill of Supply",
  CREDIT_NOTE: "Credit Note",
  DEBIT_NOTE: "Debit Note",
};

export const EINVOICE_LABEL = {
  NOT_REQUIRED: "Not required",
  REQUIRED: "Required",
  GENERATED: "Generated",
  FAILED: "Failed",
  CANCELLED: "Cancelled",
};

export const STATUS_LABEL = {
  DRAFT: "Draft",
  ISSUED: "Issued",
  CANCELLED: "Cancelled",
};

export const SUPPLY_LABEL = {
  INTRA: "Intra-State",
  INTER: "Inter-State",
  EXPORT: "Export",
};

export function badgeClass(code) {
  if (code === "GENERATED" || code === "ISSUED" || code === "Matched" || code === "OK" || code === "FILED") return "ok";
  if (code === "REQUIRED" || code === "FAILED" || (code && String(code).includes("Missing")) || (code && String(code).includes("mismatch"))) return "warn";
  if (code === "CANCELLED" || code === "overdue") return "bad";
  return "info";
}

export function periodPretty(fp) {
  if (!fp || fp.length < 6) return fp || "";
  const months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
  const m = Number(fp.slice(0, 2));
  return `${months[m - 1] || fp} ${fp.slice(2)}`;
}

export function indianDate(iso) {
  if (!iso) return "";
  const d = String(iso).slice(0, 10);
  const parts = d.split("-");
  if (parts.length !== 3) return iso;
  return `${parts[2]}-${parts[1]}-${parts[0]}`;
}
