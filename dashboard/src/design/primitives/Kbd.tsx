import React from "react";
import styles from "./Kbd.module.css";

export const Kbd: React.FC<React.HTMLAttributes<HTMLElement>> = ({ children, className, ...props }) => {
  return (
    <kbd className={`${styles.kbd} ${className || ""}`} {...props}>
      {children}
    </kbd>
  );
};

export const KeyboardHint: React.FC<{
  label: string;
  keys: string[];
  className?: string;
}> = ({ label, keys, className }) => {
  return (
    <span className={`${styles.hint} ${className || ""}`}>
      <span>{label}</span>
      {keys.map((k) => (
        <Kbd key={k}>{k}</Kbd>
      ))}
    </span>
  );
};
