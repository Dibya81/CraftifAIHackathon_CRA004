import React, { useState } from "react";
import {
  Button,
  SeverityBadge,
  ZoneBadge,
  StatusBadge,
  StatusDot,
  Panel,
  PanelHeader,
  PanelBody,
  Input,
  Select,
  Skeleton,
  EmptyState,
  ErrorState,
  Stat,
  KeyboardHint,
  Switch,
  Tooltip,
  Table,
  NumCell,
} from "./primitives";
import { Download, Filter, AlertCircle } from "lucide-react";

export const DesignGallery: React.FC = () => {
  const [switchChecked, setSwitchChecked] = useState(true);
  const [inputValue, setInputValue] = useState("");

  return (
    <div style={{ padding: "32px", maxWidth: "1200px", margin: "0 auto", display: "flex", flexDirection: "column", gap: "32px" }}>
      <div>
        <h1 style={{ fontSize: "28px", marginBottom: "4px" }}>SiteSentinel Design Primitives Gallery</h1>
        <p style={{ color: "var(--text-muted)", fontSize: "14px" }}>
          Internal design system tokens and component showcase in control room theme.
        </p>
      </div>

      {/* Buttons */}
      <Panel>
        <PanelHeader title="Buttons & Actions" subtitle="All variants, sizes, and interactive states" />
        <PanelBody style={{ display: "flex", flexDirection: "column", gap: "16px" }}>
          <div style={{ display: "flex", gap: "12px", alignItems: "center", flexWrap: "wrap" }}>
            <Button variant="primary">Primary Action</Button>
            <Button variant="secondary" icon={<Filter size={14} />}>Secondary Filter</Button>
            <Button variant="ghost" icon={<Download size={14} />}>Ghost Download</Button>
            <Button variant="danger" icon={<AlertCircle size={14} />}>Danger Revert</Button>
            <Button variant="primary" loading>Loading Button</Button>
            <Button variant="secondary" disabled>Disabled State</Button>
          </div>
          <div style={{ display: "flex", gap: "12px", alignItems: "center" }}>
            <Button size="sm" variant="primary">Small Action</Button>
            <Button size="md" variant="primary">Medium Action</Button>
          </div>
        </PanelBody>
      </Panel>

      {/* Badges & Status Indicators */}
      <Panel>
        <PanelHeader title="Badges, Status Dots & Indicators" subtitle="High-contrast semantic indicators with icons + labels" />
        <PanelBody style={{ display: "flex", flexDirection: "column", gap: "16px" }}>
          <div style={{ display: "flex", gap: "12px", alignItems: "center", flexWrap: "wrap" }}>
            <SeverityBadge severity="LOW" />
            <SeverityBadge severity="MEDIUM" />
            <SeverityBadge severity="HIGH" />
            <ZoneBadge type="safe" name="walkway (safe)" />
            <ZoneBadge type="restricted" name="press-area (restricted)" />
            <ZoneBadge type="danger" name="crane-drop (danger)" />
            <StatusBadge status="open" />
            <StatusBadge status="acknowledged" />
          </div>
          <div style={{ display: "flex", gap: "24px", alignItems: "center" }}>
            <StatusDot status="ok" label="Pipeline Operational" />
            <StatusDot status="degraded" label="Degraded FPS (<20)" />
            <StatusDot status="down" label="Camera Signal Lost" />
          </div>
        </PanelBody>
      </Panel>

      {/* Stats & Sparklines */}
      <Panel>
        <PanelHeader title="Telemetry & Compliance Stats" subtitle="Industrial Barlow Condensed numerals with deltas and sparklines" />
        <PanelBody style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))", gap: "16px" }}>
          <Stat label="Site Compliance" value="98.4%" delta={1.2} deltaLabel="vs yesterday" sparklineData={[94, 95, 96, 95, 97, 98, 98.4]} />
          <Stat label="Processing Rate" value="25.0" unit="FPS" delta={0} deltaLabel="target met" sparklineData={[25, 25, 24.8, 25.1, 25.0]} />
          <Stat label="Inference Latency" value="38.9" unit="ms" delta={-4.5} deltaLabel="faster" sparklineData={[44, 42, 41, 39, 38.9]} />
          <Stat label="Open Incidents" value="1" delta={-50} deltaLabel="cleared" />
        </PanelBody>
      </Panel>

      {/* Form Controls */}
      <Panel>
        <PanelHeader title="Form Controls & Inputs" subtitle="Accessible inputs, selects, and switches" />
        <PanelBody style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: "16px" }}>
          <Input
            label="Search Incidents"
            aria-label="Search by ID or zone"
            value={inputValue}
            onChange={(e) => setInputValue(e.target.value)}
            helperText="Press Enter to search"
          />
          <Select
            label="Camera Device"
            options={[
              { value: "cam-01", label: "cam-01 (Fabrication Bay)" },
              { value: "cam-02", label: "cam-02 (Storage Yard)" },
            ]}
          />
          <div style={{ display: "flex", flexDirection: "column", gap: "8px", justifyContent: "center" }}>
            <span style={{ fontSize: "12px", color: "var(--text-muted)", fontWeight: 500 }}>Live Feed Toggles</span>
            <Switch
              id="switch-unack"
              checked={switchChecked}
              onCheckedChange={setSwitchChecked}
              label="Unacknowledged only"
            />
          </div>
        </PanelBody>
      </Panel>

      {/* Keyboard Shortcuts */}
      <Panel>
        <PanelHeader title="Keyboard Navigation & Hints" subtitle="Single stroke control room shortcuts" />
        <PanelBody style={{ display: "flex", gap: "24px", flexWrap: "wrap", alignItems: "center" }}>
          <KeyboardHint label="Acknowledge violation" keys={["A"]} />
          <KeyboardHint label="Toggle Present mode" keys={["P"]} />
          <KeyboardHint label="Global Command Palette" keys={["⌘", "K"]} />
          <KeyboardHint label="Jump to Live screen" keys={["G", "L"]} />
          <KeyboardHint label="Undo zone vertex" keys={["⌘", "Z"]} />
        </PanelBody>
      </Panel>

      {/* Dense Table */}
      <Panel>
        <PanelHeader title="Dense Data Table" subtitle="Sticky header with right-aligned tabular numerals" />
        <PanelBody>
          <Table>
            <thead>
              <tr>
                <th>Zone ID</th>
                <th>Type</th>
                <th>Required PPE</th>
                <th style={{ textAlign: "right" }}>Incidents (24h)</th>
                <th style={{ textAlign: "right" }}>Compliance Rate</th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <td>walkway</td>
                <td><ZoneBadge type="safe" name="safe" /></td>
                <td>helmet</td>
                <NumCell>1</NumCell>
                <NumCell>99.2%</NumCell>
              </tr>
              <tr>
                <td>press-area</td>
                <td><ZoneBadge type="restricted" name="restricted" /></td>
                <td>helmet, vest</td>
                <NumCell>3</NumCell>
                <NumCell>96.4%</NumCell>
              </tr>
              <tr>
                <td>crane-drop</td>
                <td><ZoneBadge type="danger" name="danger" /></td>
                <td>helmet, vest</td>
                <NumCell>0</NumCell>
                <NumCell>100.0%</NumCell>
              </tr>
            </tbody>
          </Table>
        </PanelBody>
      </Panel>

      {/* Skeletons & Feedback States */}
      <Panel>
        <PanelHeader title="Feedback & Loading Skeletons" subtitle="Zero layout-shift loading and error states" />
        <PanelBody style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "24px" }}>
          <div style={{ display: "flex", flexDirection: "column", gap: "12px" }}>
            <Skeleton height="32px" width="60%" />
            <Skeleton height="16px" width="90%" />
            <Skeleton height="16px" width="80%" />
            <Skeleton height="120px" width="100%" />
          </div>
          <div style={{ display: "flex", flexDirection: "column", gap: "16px" }}>
            <EmptyState
              title="No incidents match these filters"
              description="Adjust your search criteria or clear active filters."
              action={<Button variant="secondary" size="sm">Clear filters</Button>}
            />
            <ErrorState
              title="Camera signal lost"
              message="Check the USB cable or RTSP address in config/sentinel.yaml."
              onRetry={() => {}}
            />
            <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
              <Tooltip content="Tooltip explains industrial context without noise">
                <Button variant="ghost" size="sm">Hover for Tooltip</Button>
              </Tooltip>
            </div>
          </div>
        </PanelBody>
      </Panel>
    </div>
  );
};
