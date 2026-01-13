import React from "react";
import { createPortal } from "react-dom";
import { SvgButton } from "../SvgButton/SvgButton";
import { SVGS } from "../../assets/svgs";

type TModalProps = {
  children: React.ReactNode;
  hide: () => void;
  visible?: boolean;
  extraButtons?: React.ReactNode;
  minHeight?: string;
  header?: React.ReactNode;
};

export const Modal = ({
  children,
  hide,
  visible = true,
  extraButtons = null,
  minHeight = "50vh",
  header = null,
}: TModalProps) => {
  if (!visible) return null;

  return createPortal(
    <div className="fixed inset-0 flex items-center justify-center z-50 overflow-hidden">
      {/* Backdrop */}
      <div 
        className="fixed inset-0 bg-black/70 backdrop-blur-sm" 
        onClick={hide}
      ></div>
      
      {/* Modal Content */}
      <div 
        className="relative bg-[rgba(255,255,255,0.05)] backdrop-blur-md border border-[rgba(255,255,255,0.1)] rounded-2xl shadow-lg w-[min(98%,900px)] max-w-full mx-4 max-h-[90vh] overflow-y-auto overflow-x-hidden [scrollbar-width:thin] [scrollbar-color:rgba(255,255,255,0.1)_transparent]"
        style={{ minHeight }}
      >
        {/* Close button and extra buttons */}
        <div className="flex justify-end items-center gap-2 p-2 md:p-4">
          {extraButtons}
          <SvgButton
            extraClass="pressable danger-on-hover svg-danger"
            onClick={hide}
            svg={SVGS.close}
            aria-label="Close modal"
          />
        </div>

        {/* Header */}
        {header && (
          <section className="px-4 md:px-8 pb-2 md:pb-4">
            {header}
          </section>
        )}
        
        {/* Content */}
        <section className="px-4 md:px-8 pb-8 overflow-x-auto max-w-full">
          {children}
        </section>
      </div>
    </div>,
    document.body
  );
};
