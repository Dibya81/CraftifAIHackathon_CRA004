import React from "react";
import { AlertTriangle, Inbox, RefreshCw } from "lucide-react";
import { Button } from "./Button";
import styles from "./Feedback.module.css";

interface SkeletonProps extends React.HTMLAttributes<HTMLDivElement> {
  width?: string | number;
  height?: string | number;
}

export const Skeleton: React.FC<SkeletonProps> = ({ width, height, className, style, ...props }) => {
  return (
    <div
      className={`${styles.skeleton} ${className || ""}`}
      style={{
        width: width ?? "100%",
        height: height ?? "20px",
        ...style,
      }}
      aria-hidden="true"
      {...props}
    />
  );
};

interface EmptyStateProps {
  title: string;
  description?: string;
  icon?: React.ReactNode;
  action?: React.ReactNode;
  className?: string;
}

export const EmptyState: React.FC<EmptyStateProps> = ({
  title,
  description,
  icon,
  action,
  className,
}) => {
  return (
    <div className={`${styles.stateBox} ${className || ""}`}>
      <div className={styles.stateIcon}>{icon || <Inbox />}</div>
      <h3 className={styles.stateTitle}>{title}</h3>
      {description && <p className={styles.stateDescription}>{description}</p>}
      {action && <div>{action}</div>}
    </div>
  );
};

interface ErrorStateProps {
  title?: string;
  message: string;
  onRetry?: () => void;
  className?: string;
}

export const ErrorState: React.FC<ErrorStateProps> = ({
  title = "Failed to load data",
  message,
  onRetry,
  className,
}) => {
  return (
    <div className={`${styles.stateBox} ${className || ""}`} role="alert">
      <div className={`${styles.stateIcon} ${styles.errorIcon}`}>
        <AlertTriangle />
      </div>
      <h3 className={styles.stateTitle}>{title}</h3>
      <p className={styles.stateDescription}>{message}</p>
      {onRetry && (
        <Button variant="secondary" size="sm" icon={<RefreshCw size={14} />} onClick={onRetry}>
          Retry
        </Button>
      )}
    </div>
  );
};
