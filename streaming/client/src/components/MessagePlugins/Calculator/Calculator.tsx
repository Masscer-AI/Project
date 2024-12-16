import React, { useEffect, useState } from "react";
import { calculateOperations } from "../../../modules/utils";
import { OperationStep } from "../../../modules/utils";
import toast from "react-hot-toast";
import { useTranslation } from "react-i18next";

type TCalculationSchema = {
  operations: OperationStep[];
};

export const Calculator = ({ operations }: TCalculationSchema) => {
  const { t } = useTranslation();
  const [result, setResult] = useState<OperationStep[] | null>(null);

  const handleCalculate = () => {
    const result = calculateOperations(operations);
    setResult(result);
  };

  useEffect(() => {
    handleCalculate();
  }, []);

  return (
    <div className="flex-y gap-medium bg-hovered padding-medium rounded justify-center my-medium">
      {result?.map((op, index) => (
        <div className="flex-y gap-small " key={index}>
          <p>
            {index + 1}. {op.label}
            <span className="text-secondary"> ({op.arguments.join(", ")})</span>
          </p>
          <div className="bg-hovered padding-small rounded d-flex gap-small align-center fit-content">
            <span>{op.result_name}=</span>
            <code
              onClick={() => {
                // Copy the content to clipboard
                if (op.result_value) {
                  navigator.clipboard.writeText(op.result_value.toString());
                  toast.success(t("copied"))
                }
              }}
              className="active-on-hover pointer pressable"
            >
              {op.result_value}
            </code>
          </div>
        </div>
      ))}
    </div>
  );
};
