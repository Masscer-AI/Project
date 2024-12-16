import React, { useEffect, useState } from "react";
import { SvgButton } from "../SvgButton/SvgButton";
import toast from "react-hot-toast";

export const SliderInput = ({
  checked,
  onChange,
  labelTrue = "",
  labelFalse = "",
  extraClass = "",
  keepActive = false,
  svgTrue = null,
  svgFalse = null,
}: {
  checked: boolean;
  onChange: (checked: boolean) => void;
  labelTrue?: string;
  labelFalse?: string;
  extraClass?: string;
  keepActive?: boolean;
  svgTrue?: React.ReactNode;
  svgFalse?: React.ReactNode;
}) => {
  const [innerChecked, setInnerChecked] = useState(checked);
  const slideInfo = {
    true: {
      label: labelTrue,
      svg: svgTrue,
    },
    false: {
      label: labelFalse,
      svg: svgFalse,
    },
  };

  useEffect(() => {
    setInnerChecked(checked);
  }, [checked]);

  return (
    <div className={`d-flex gap-medium ${extraClass} align-center `}>
      <label className={`switch `}>
        <input
          tabIndex={0}
          type="checkbox"
          checked={innerChecked}
          onChange={(e) => onChange(e.target.checked)}
        />

        <div className={`slider ${keepActive && "keep-active"}`}></div>
      </label>
      <div className="d-flex gap-small align-center ">
        {innerChecked ? (
          <>
            <p>{slideInfo.true.label}</p>
            <div className="svg-mini">{slideInfo.true.svg}</div>
          </>
        ) : (
          <>
            <div className="svg-mini">{slideInfo.false.svg}</div>
            <p>{slideInfo.false.label}</p>
          </>
        )}
      </div>
    </div>
  );
};
