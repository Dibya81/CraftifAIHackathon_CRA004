import React from "react";
import { ArrowUpRight, ArrowDownRight, Minus } from "lucide-react";
import styles from "./Stat.module.css";

interface SparklineProps {
  data: number[];
  width?: number;
  height?: number;
  color?: string;
  className?: string;
}

export const Sparkline: React.FC<SparklineProps> = ({
  data,
  width = 80,
  height = 24,
  color = "var(--info)",
  className,
}) => {
  if (!data || data.length < 2) return null;

  const min = Math.min(...data);
  const max = Math.max(...data);
  const range = max - min || 1;
  const padding = 2;

  const points = data
    .map((val, idx) => {
      const x = padding + (idx / (data.length - 1)) * (width - 2 * padding);
      const y = height - padding - ((val - min) / range) * (height - 2 * padding);
      return `${x.toFixed(1)},${y.toFixed(1)}`;
    })
    .join(" ");

  return (
    <svg
      width={width}
      height={height}
      className={`${styles.sparklineSvg} ${className || ""}`}
      aria-hidden="true"
    >
      <polyline
        fill="none"
        stroke={color}
        strokeWidth="1.5"
        strokeLinecap="round"
        strokeLinejoin="round"
        points={points}
      />
    </svg>
  );
};

interface StatProps {
  label: string;
  value: string | number;
  unit?: string;
  delta?: number;
  deltaLabel?: string;
  sparklineData?: number[];
  className?: string;
}

export const Stat: React.FC<StatProps> = ({
  label,
  value,
  unit,
  delta,
  deltaLabel,
  sparklineData,
  className,
}) => {
  const isPositive = delta !== undefined && delta > 0;
  const isNegative = delta !== undefined && delta < 0;
  const deltaClass = isPositive
    ? styles.deltaPositive
    : isNegative
    ? styles.deltaNegative
    : styles.deltaNeutral;

  return (
    <div className={`${styles.statCard} ${className || ""}`}>
      <span className={styles.label}>{label}</span>
      <div className={styles.valueRow}>
        <span className={styles.value}>
          {value}
          {unit && <span className={styles.unit}> {unit}</span>}
        </span>
        {delta !== undefined && (
          <span className={`${styles.delta} ${deltaClass}`}>
            {isPositive ? (
              <ArrowUpRight size={14} />
            ) : isNegative ? (
              <ArrowDownRight size={14} />
            ) : (
              <Minus size={14} />
            )}
            <span>{Math.abs(delta)}%</span>
            {deltaLabel && <span className={styles.unit}>{deltaLabel}</span>}
          </span>
        )}
      </div>
      {sparklineData && sparklineData.length > 1 && (
        <Sparkline data={sparklineData} width={120} height={20} />
      )}
    </div>
  );
};
