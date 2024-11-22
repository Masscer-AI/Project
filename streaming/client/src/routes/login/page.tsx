import React, { useState } from "react";
import axios from "axios";
import { Toaster, toast } from "react-hot-toast";
import "./page.css";
import { useNavigate } from "react-router-dom";
import { API_URL } from "../../modules/constants";
import { SimpleForm } from "../../components/SimpleForm/SimpleForm";
import { SvgButton } from "../../components/SvgButton/SvgButton";
import { SVGS } from "../../assets/svgs";
import { useTranslation } from "react-i18next";

export default function Login() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [message, setMessage] = useState("");
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
      navigate("/chat");
    } catch (error) {
      setMessage(error.response?.data?.detail || t("an-error-occurred"));
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
          <div className="simple-form-group pos-relative">
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
              svg={showPassword ? SVGS.eyeClosed : SVGS.eye}
              onClick={() => setShowPassword(!showPassword)}
            />
          </div>
          <SvgButton
            onClick={handleSubmit}
            text={!isLoading ? t("login") : t("loading")}
            extraClass="w-100 padding-medium button bg-active pressable"
          />
          <SvgButton
            extraClass="w-100 padding-medium button bg-secondary"
            text={t("go-to-signup")}
            onClick={() => navigate("/signup")}
          />
        </form>
      </SimpleForm>
    </div>
  );
}
