import React from "react";

export const Card = ({
  children,
  onClick,
}: {
  children: React.ReactNode;
  onClick: () => void;
}) => {
  return (
    <div className="card clickeable" onClick={onClick}>
      {children}
    </div>
  );
};
