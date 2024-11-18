import React, { useState } from "react";
import axios from "axios";
import { Toaster, toast } from "react-hot-toast";
import "./page.css";
import { useNavigate } from "react-router-dom";
import { API_URL } from "../../modules/constants";
import { SimpleForm } from "../../components/SimpleForm/SimpleForm";
import { SvgButton } from "../../components/SvgButton/SvgButton";
import { SVGS } from "../../assets/svgs";

export default function Login() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [message, setMessage] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const navigate = useNavigate();

  const handleSubmit = async (e: React.MouseEvent<HTMLButtonElement>) => {
    // e.preventDefault();
    setIsLoading(true);
    const endpoint = "/v1/auth/login";
    const payload = { email, password };
    try {
      console.log(message);

      const response = await axios.post(API_URL + endpoint, payload);
      setMessage(response.data.message);
      if (response.data.token) {
        localStorage.setItem("token", response.data.token);
      }
      toast.success("Successfully logged in!");
      navigate("/chat");
    } catch (error) {
      setMessage(error.response?.data?.detail || "An error occurred");
      toast.error("An error occurred");
    }
    setIsLoading(false);
  };

  return (
    <div className="login-component">
      <SimpleForm>
        <h2 className="simple-form-title">Login</h2>
        <form onSubmit={(e) => e.preventDefault()}>
          <div className="simple-form-group">
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
              name="email"
              placeholder="Email"
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
              name="password"
              placeholder="Password"
              className="input padding-medium"
              autoComplete="current-password"
            />
            <SvgButton
              extraClass="pos-absolute  right-zero top-middle"
              svg={showPassword ? SVGS.eyeClosed : SVGS.eye}
              onClick={() => setShowPassword(!showPassword)}
            />
          </div>
          <button
            onClick={handleSubmit}
            type="submit"
            className="w-100 padding-medium button bg-active"
          >
            {!isLoading ? "Login" : "Loading..."}
          </button>
          <button
            onClick={() => navigate("/signup")}
            className="button bg-secondary w-100 padding-medium"
          >
            Switch to Signup
          </button>
        </form>
      </SimpleForm>
    </div>
  );
}
