import React from "react";
import styles from "./StatusDot.module.css";

export type StatusDotState = "ok" | "degraded" | "down";

interface StatusDotProps {
  status: StatusDotState;
  label?: string;
  className?: string;
}

export const StatusDot: React.FC<StatusDotProps> = ({ status, label, className }) => {
  return (
    <span className={`${styles.statusDotWrapper} ${className || ""}`} title={label || status}>
      <span className={`${styles.dot} ${styles[status]}`} aria-hidden="true" />
      {label && <span>{label}</span>}
    </span>
  );
};
