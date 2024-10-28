import React from "react";

export const Pill = ({
  children,
  extraClass = "",
  onClick = () => {},
}: {
  children: React.ReactNode;
  extraClass?: string;
  onClick?: () => void;
}) => {
  return (
    <span onClick={onClick} className={`pill ${extraClass}`}>
      {children}
    </span>
  );
};
