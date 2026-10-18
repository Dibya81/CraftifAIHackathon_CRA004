import React from "react";
import * as RadixSwitch from "@radix-ui/react-switch";
import * as RadixTooltip from "@radix-ui/react-tooltip";
import * as RadixDialog from "@radix-ui/react-dialog";
import * as RadixTabs from "@radix-ui/react-tabs";
import styles from "./RadixWrappers.module.css";

/* Switch */
export interface SwitchProps {
  checked: boolean;
  onCheckedChange: (checked: boolean) => void;
  label?: string;
  disabled?: boolean;
  id?: string;
  className?: string;
}

export const Switch: React.FC<SwitchProps> = ({
  checked,
  onCheckedChange,
  label,
  disabled,
  id,
  className,
}) => {
  return (
    <div style={{ display: "inline-flex", alignItems: "center", gap: "8px" }} className={className}>
      <RadixSwitch.Root
        className={styles.switchRoot}
        checked={checked}
        onCheckedChange={onCheckedChange}
        disabled={disabled}
        id={id}
      >
        <RadixSwitch.Thumb className={styles.switchThumb} />
      </RadixSwitch.Root>
      {label && (
        <label htmlFor={id} style={{ fontSize: "14px", cursor: disabled ? "not-allowed" : "pointer" }}>
          {label}
        </label>
      )}
    </div>
  );
};

/* Tooltip */
export const Tooltip: React.FC<{
  content: React.ReactNode;
  children: React.ReactNode;
}> = ({ content, children }) => {
  return (
    <RadixTooltip.Provider delayDuration={200}>
      <RadixTooltip.Root>
        <RadixTooltip.Trigger asChild>{children}</RadixTooltip.Trigger>
        <RadixTooltip.Portal>
          <RadixTooltip.Content className={styles.tooltipContent} sideOffset={4}>
            {content}
          </RadixTooltip.Content>
        </RadixTooltip.Portal>
      </RadixTooltip.Root>
    </RadixTooltip.Provider>
  );
};

/* Dialog */
export const Dialog = RadixDialog.Root;
export const DialogTrigger = RadixDialog.Trigger;
export const DialogClose = RadixDialog.Close;

export const DialogContent: React.FC<{
  title: string;
  description?: string;
  children: React.ReactNode;
  className?: string;
}> = ({ title, description, children, className }) => {
  return (
    <RadixDialog.Portal>
      <RadixDialog.Overlay className={styles.dialogOverlay} />
      <RadixDialog.Content className={`${styles.dialogContent} ${className || ""}`}>
        <RadixDialog.Title style={{ fontFamily: "var(--font-display)", fontSize: "20px", marginBottom: "4px" }}>
          {title}
        </RadixDialog.Title>
        {description && (
          <RadixDialog.Description style={{ color: "var(--text-muted)", fontSize: "14px", marginBottom: "16px" }}>
            {description}
          </RadixDialog.Description>
        )}
        {children}
      </RadixDialog.Content>
    </RadixDialog.Portal>
  );
};

/* Tabs */
export const Tabs = RadixTabs.Root;
export const TabsList: React.FC<RadixTabs.TabsListProps> = ({ className, ...props }) => (
  <RadixTabs.List className={`${styles.tabsList} ${className || ""}`} {...props} />
);
export const TabsTrigger: React.FC<RadixTabs.TabsTriggerProps> = ({ className, ...props }) => (
  <RadixTabs.Trigger className={`${styles.tabsTrigger} ${className || ""}`} {...props} />
);
export const TabsContent = RadixTabs.Content;

/* Dense Table */
export const Table: React.FC<React.TableHTMLAttributes<HTMLTableElement>> = ({
  children,
  className,
  ...props
}) => {
  return (
    <div className={styles.tableContainer}>
      <table className={`${styles.table} ${className || ""}`} {...props}>
        {children}
      </table>
    </div>
  );
};

export const NumCell: React.FC<React.TdHTMLAttributes<HTMLTableCellElement>> = ({
  children,
  className,
  ...props
}) => {
  return (
    <td className={`${styles.numCell} ${className || ""}`} {...props}>
      {children}
    </td>
  );
};
