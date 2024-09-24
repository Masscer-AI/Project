import React, { useState } from "react";
import axios from "axios";
import { Toaster, toast } from "react-hot-toast";
import "./page.css";
import { useNavigate } from "react-router-dom";
import { API_URL } from "../../modules/constants";
import { SimpleForm } from "../../components/SimpleForm/SimpleForm";

export default function Signup() {
  const [username, setUsername] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [message, setMessage] = useState("");
  console.log(message);

  const navigate = useNavigate();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const endpoint = "/v1/auth/signup";
    const payload = { username, email, password };
    try {
      const response = await axios.post(API_URL + endpoint, payload);
      setMessage(response.data.message);
      if (response.data.token) {
        localStorage.setItem("token", response.data.token);
      }
      toast.success("User created successfully! Please log in");
      navigate("/login");
    } catch (error) {
      setMessage(error.response?.data?.detail || "An error occurred");
      toast.error("An error occurred");
    }
  };

  return (
    <div className="signup-component">
      <Toaster />
      <SimpleForm>
        <h2 className="simple-form-title">Sign Up</h2>
        <form onSubmit={handleSubmit}>
          <div className="simple-form-group">
            <label className="simple-form-label">Username:</label>
            <input
              type="text"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              required
              className="simple-form-input"
            />
          </div>
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
            Signup
          </button>
        </form>
        <button
          onClick={() => navigate("/login")}
          className="simple-form-button"
        >
          Switch to Login
        </button>
      </SimpleForm>
    </div>
  );
}
