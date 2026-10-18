import React from "react";
import styles from "./Panel.module.css";

interface PanelProps extends React.HTMLAttributes<HTMLDivElement> {
  children: React.ReactNode;
}

export const Panel: React.FC<PanelProps> = ({ children, className, ...props }) => {
  return (
    <div className={`${styles.panel} ${className || ""}`} {...props}>
      {children}
    </div>
  );
};

interface PanelHeaderProps {
  title: string;
  subtitle?: string;
  icon?: React.ReactNode;
  actions?: React.ReactNode;
  className?: string;
}

export const PanelHeader: React.FC<PanelHeaderProps> = ({
  title,
  subtitle,
  icon,
  actions,
  className,
}) => {
  return (
    <div className={`${styles.header} ${className || ""}`}>
      <div className={styles.titleGroup}>
        {icon && <span aria-hidden="true">{icon}</span>}
        <div>
          <h2 className={styles.title}>{title}</h2>
          {subtitle && <p className={styles.subtitle}>{subtitle}</p>}
        </div>
      </div>
      {actions && <div className={styles.actions}>{actions}</div>}
    </div>
  );
};

export const PanelBody: React.FC<React.HTMLAttributes<HTMLDivElement>> = ({
  children,
  className,
  ...props
}) => {
  return (
    <div className={`${styles.body} ${className || ""}`} {...props}>
      {children}
    </div>
  );
};

export const PanelFooter: React.FC<React.HTMLAttributes<HTMLDivElement>> = ({
  children,
  className,
  ...props
}) => {
  return (
    <div className={`${styles.footer} ${className || ""}`} {...props}>
      {children}
    </div>
  );
};
