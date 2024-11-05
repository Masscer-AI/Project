import React from "react";
import { Position, Handle } from "@xyflow/react";

export const NodeTemplate = ({
  children,
  bgColor = "bg-active",
  data,
}: {
  children: React.ReactNode;
  bgColor?: string;
  data: any;
}) => {
  return (
    <div
      style={{
        backgroundColor: bgColor,
        maxWidth: "300px",
      }}
      className={`padding-big rounded overflow-hidden ${data.isActive ? "fancy-gradient" : ""}`}
    >
      <Handle
        style={{ background: "yellowgreen", width: "10px", height: "10px" }}
        type="target"
        position={Position.Top}
      />
      {children}
      <Handle
        type="source"
        position={Position.Bottom}
        style={{ background: "red", width: "10px", height: "10px" }}
      />
    </div>
  );
};
