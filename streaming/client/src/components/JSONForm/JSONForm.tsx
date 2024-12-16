import React, { useState } from "react";
import { Textarea } from "../SimpleForm/Textarea";

type TField = {
  type: string;
  label: string;
};

interface JSONFormProps {
  data: Record<string, any>;
  hiddenKeys?: string[];
  onSubmit: (formData: Record<string, any>) => void;
  onKeyChange?: (key: string, value: any) => void;
  fieldMapping?: Record<string, TField>;
}

export const JSONForm: React.FC<JSONFormProps> = ({
  data,
  hiddenKeys = [],
  onSubmit,
  onKeyChange,
  fieldMapping = {},
}) => {
  const [formData, setFormData] = useState<Record<string, any>>(data);

  const handleChange = (key: string, value: any) => {
    setFormData({ ...formData, [key]: value });
    onKeyChange?.(key, value);
  };

  const handleSubmit = (event: React.FormEvent) => {
    event.preventDefault();
    onSubmit(formData);
  };

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
              value={formData[key] || ""}
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
            placeholder={field.label}
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

  return (
    <form onSubmit={handleSubmit} className="flex-y gap-big">
      {Object.keys(data).map((key) => {
        if (hiddenKeys.includes(key)) return null;
        return renderInput(key, data[key]);
      })}
    </form>
  );
};
