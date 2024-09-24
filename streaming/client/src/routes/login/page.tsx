import React, { useState } from "react";
import axios from "axios";
import { Toaster, toast } from "react-hot-toast";
import "./page.css";
import { useNavigate } from "react-router-dom";
import { API_URL } from "../../modules/constants";
import { SimpleForm } from "../../components/SimpleForm/SimpleForm";

export default function Login() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [message, setMessage] = useState("");

  const navigate = useNavigate();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const endpoint = "/v1/auth/login";
    const payload = { username: email, password };
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
  };

  return (
    <div className="login-component">
      <Toaster />
      <SimpleForm>
        <h2 className="simple-form-title">Login</h2>
        <form onSubmit={handleSubmit}>
          <div className="simple-form-group">
            <label className="simple-form-label">Email:</label>
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
              className="simple-form-input"
              autoComplete="email"
            />
          </div>
          <div className="simple-form-group">
            <label className="simple-form-label">Password:</label>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              className="simple-form-input"
              autoComplete="current-password"
            />
          </div>
          <button type="submit" className="simple-form-button">
            Login
          </button>
        </form>
        <button
          onClick={() => navigate("/signup")}
          className="simple-form-button"
        >
          Switch to Signup
        </button>
      </SimpleForm>
    </div>
  );
}
