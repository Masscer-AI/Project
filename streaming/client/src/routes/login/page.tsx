import React, { useState } from "react";
import axios from "axios";
import { Toaster, toast } from "react-hot-toast";
import "./page.css";
import { useNavigate } from "react-router-dom";
import { API_URL } from "../../modules/constants";
import { SimpleForm } from "../../components/SimpleForm/SimpleForm";
import { SvgButton } from "../../components/SvgButton/SvgButton";
import { Icon } from "../../components/Icon/Icon";
import { useTranslation } from "react-i18next";

type TMessage = {
  text: string;
  type: "error" | "success";
};

export default function Login() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [message, setMessage] = useState<TMessage>({
    text: "",
    type: "error",
  });
  const [showPassword, setShowPassword] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const navigate = useNavigate();
  const { t } = useTranslation();

  const handleSubmit = async () => {
    if (!email || !password) {
      toast.error(t("email-and-password-required"));
      return;
    }

    setIsLoading(true);
    const endpoint = "/v1/auth/login";
    const payload = { email, password };
    try {
      const response = await axios.post(API_URL + endpoint, payload);
      setMessage(response.data.message);
      if (response.data.token) {
        localStorage.setItem("token", response.data.token);
      }
      toast.success(t("successfully-logged-in"));
      setMessage({ text: t("successfully-logged-in"), type: "success" });
      navigate("/chat");
    } catch (error) {
      console.error("LOGIN ERROR: ", error);
      if (error.code === "ERR_NETWORK") {
        setMessage({ text: t("network-error"), type: "error" });
      } else {
        setMessage({
          text: error.response?.data?.detail || t("an-error-occurred"),
          type: "error",
        });
      }
      toast.error(t("an-error-occurred"));
    }
    setIsLoading(false);
  };

  const handleKeyUp = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Enter") {
      handleSubmit();
    }
  };

  return (
    <div className="login-component">
      <SimpleForm>
        <h2 className="simple-form-title">{t("login")}</h2>
        <form onSubmit={(e) => e.preventDefault()}>
          <div className="simple-form-group">
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
              name="email"
              placeholder={t("email")}
              className="input padding-medium"
              autoComplete="email"
            />
          </div>
          <div className="pos-relative">
            <input
              type={showPassword ? "text" : "password"}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              onKeyUp={handleKeyUp}
              name="password"
              placeholder={t("password")}
              className="input padding-medium"
              autoComplete="current-password"
            />
            <SvgButton
              tabIndex={-1}
              extraClass="pos-absolute right-zero top-middle padding-small"
              svg={showPassword ? <Icon name="EyeOff" size={20} /> : <Icon name="Eye" size={20} />}
              onClick={() => setShowPassword(!showPassword)}
            />
            {/* <p className="text-small text-center text-gray">
              {t("forgot-password")}
            </p> */}
          </div>
          <p
            className={`text-small padding-medium no-margin text-center ${message.type === "error" ? "text-error" : "text-success"}`}
          >
            {message.text}
          </p>
          <div className="flex-y gap-small">
            <SvgButton
              onClick={handleSubmit}
              text={!isLoading ? t("login") : t("loading")}
              extraClass="w-100 padding-medium button bg-active pressable"
            />
          </div>
        </form>
      </SimpleForm>
    </div>
  );
}
