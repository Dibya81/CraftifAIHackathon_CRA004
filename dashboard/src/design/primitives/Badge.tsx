import { Info, AlertTriangle, AlertOctagon, CheckCircle2 } from "lucide-react";
import styles from "./Badge.module.css";

export type BadgeSemantic = "info" | "warn" | "danger" | "ok" | "neutral";
export type SeverityType = "LOW" | "MEDIUM" | "HIGH";
export type ZoneType = "safe" | "restricted" | "danger";

interface BadgeProps extends React.HTMLAttributes<HTMLSpanElement> {
  variant?: BadgeSemantic;
  icon?: React.ReactNode;
  children: React.ReactNode;
}

export const Badge: React.FC<BadgeProps> = ({
  variant = "neutral",
  icon,
  children,
  className,
  ...props
}) => {
  return (
    <span className={`${styles.badge} ${styles[variant]} ${className || ""}`} {...props}>
      {icon && <span aria-hidden="true">{icon}</span>}
      <span>{children}</span>
    </span>
  );
};

export const SeverityBadge: React.FC<{ severity: SeverityType; className?: string }> = ({
  severity,
  className,
}) => {
  const config = {
    LOW: { variant: "info" as const, icon: <Info />, label: "Low" },
    MEDIUM: { variant: "warn" as const, icon: <AlertTriangle />, label: "Medium" },
    HIGH: { variant: "danger" as const, icon: <AlertOctagon />, label: "High" },
  }[severity] || { variant: "neutral" as const, icon: <Info />, label: severity };

  return (
    <Badge variant={config.variant} icon={config.icon} className={className}>
      {config.label}
    </Badge>
  );
};

export const ZoneBadge: React.FC<{ type: ZoneType | string; name?: string; className?: string }> = ({
  type,
  name,
  className,
}) => {
  const normType = (type || "").toLowerCase();
  const variant: BadgeSemantic =
    normType === "danger" ? "danger" : normType === "restricted" ? "warn" : "info";

  return (
    <Badge variant={variant} className={className}>
      {name || type}
    </Badge>
  );
};

export const StatusBadge: React.FC<{ status: "open" | "acknowledged"; className?: string }> = ({
  status,
  className,
}) => {
  if (status === "acknowledged") {
    return (
      <Badge variant="ok" icon={<CheckCircle2 />} className={className}>
        Acknowledged
      </Badge>
    );
  }
  return (
    <Badge variant="warn" icon={<AlertTriangle />} className={className}>
      Open
    </Badge>
  );
};
