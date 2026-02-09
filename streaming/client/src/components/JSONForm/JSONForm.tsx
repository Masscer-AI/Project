import React, { useEffect, useState } from "react";
import { Textarea } from "../SimpleForm/Textarea";
import { IconDeviceFloppy } from "@tabler/icons-react";

type TField = {
  type: string;
  label: string;
};

export type TJSONFormData = Record<string, any>;

interface JSONFormProps {
  data: TJSONFormData;
  hiddenKeys?: string[];
  submitText?: string;
  onSubmit?: (formData: TJSONFormData) => void;
  onKeyChange?: (key: string, value: any) => void;
  fieldMapping?: Record<string, TField>;
}

export const JSONForm: React.FC<JSONFormProps> = ({
  data,
  hiddenKeys = [],
  submitText = "",
  onSubmit,
  onKeyChange,
  fieldMapping = {},
}) => {
  const [formData, setFormData] = useState<TJSONFormData>(data);
  const [hoveredButton, setHoveredButton] = useState<string | null>(null);

  const handleChange = (key: string, value: any) => {
    setFormData({ ...formData, [key]: value });
    onKeyChange?.(key, value);
  };

  const handleSubmit = (event: React.FormEvent) => {
    event.preventDefault();
    onSubmit?.(formData);
  };

  useEffect(() => {
    setFormData(data);
  }, [data]);

  const renderInput = (key: string, value: any) => {
    const field = fieldMapping[key] || { type: typeof value, label: key };

    switch (field.type) {
      case "string":
        return (
          <div key={key} className="d-flex gap-medium align-center">
            <label>{field.label}</label>
            <input
              className="input"
              type="text"
              defaultValue={formData[key] || ""}
              onChange={(e) => handleChange(key, e.target.value)}
            />
          </div>
        );
      case "textarea":
        return (
          <Textarea
            key={key}
            defaultValue={formData[key] || ""}
            onChange={(value) => handleChange(key, value)}
            label={field.label}
          />
        );
      case "number":
        return (
          <div key={key} className="d-flex gap-medium align-center">
            <label>{field.label}</label>
            <input
              className="input"
              type="number"
              value={formData[key] || ""}
              onChange={(e) => handleChange(key, Number(e.target.value))}
            />
          </div>
        );
      case "boolean":
        return (
          <div key={key} className="d-flex gap-medium align-center">
            <label>{field.label}</label>
            <input
              className="input"
              type="checkbox"
              checked={!!formData[key]}
              onChange={(e) => handleChange(key, e.target.checked)}
            />
          </div>
        );
      case "date":
        return (
          <div key={key} className="d-flex gap-medium align-center">
            <label>{field.label}</label>
            <input
              className="input"
              type="date"
              value={formData[key] || ""}
              onChange={(e) => handleChange(key, e.target.value)}
            />
          </div>
        );
      case "image":
        return (
          <div key={key} className="d-flex gap-medium align-center">
            <label>{field.label}</label>
            <input
              type="file"
              accept="image/*"
              className="input"
              onChange={(e) => {
                // Save the iamge as B64
                const file = e.target.files?.[0];
                if (!file) return;
                const reader = new FileReader();
                reader.readAsDataURL(file);
                reader.onload = () => {
                  handleChange(key, reader.result as string);
                };
              }}
            />
            {formData[key] && (
              <div className="circle-image">
                <img src={formData[key]} alt={field.label} width={50} />
              </div>
            )}
          </div>
        );
      default:
        return null;
    }
  };

  // Collect all keys: from data + from fieldMapping (for fields not in data yet)
  const allKeys = new Set([
    ...Object.keys(data),
    ...Object.keys(fieldMapping),
  ]);

  return (
    <form onSubmit={handleSubmit} className="flex-y gap-big">
      {Array.from(allKeys).map((key) => {
        if (hiddenKeys.includes(key)) return null;
        return renderInput(key, data[key]);
      })}
      {onSubmit && (
        <button
          type="submit"
          className={`px-8 py-3 rounded-full font-normal text-sm cursor-pointer border flex items-center gap-2 w-full justify-center ${
            hoveredButton === 'save' 
              ? 'bg-white text-gray-800 border-[rgba(156,156,156,0.3)]' 
              : 'bg-[rgba(35,33,39,0.5)] text-white border-[rgba(156,156,156,0.3)] hover:bg-[rgba(35,33,39,0.8)]'
          }`}
          style={{ transform: 'none' }}
          onMouseEnter={() => setHoveredButton('save')}
          onMouseLeave={() => setHoveredButton(null)}
        >
          <IconDeviceFloppy name="Save" size={20} />
          <span>{submitText}</span>
        </button>
      )}
    </form>
  );
};
