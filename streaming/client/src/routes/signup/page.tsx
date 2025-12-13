import React, { useEffect, useState } from "react";
import axios from "axios";
import { Toaster, toast } from "react-hot-toast";
import "./page.css";
import { useNavigate, useSearchParams } from "react-router-dom";
import { API_URL, DEFAULT_ORGANIZATION_ID } from "../../modules/constants";
import { SimpleForm } from "../../components/SimpleForm/SimpleForm";
import { useTranslation } from "react-i18next";

export default function Signup() {
  const [username, setUsername] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [message, setMessage] = useState("");
  const [organization, setOrganization] = useState<any>(null);
  const [loading, setLoading] = useState(false);
  const [loadingOrg, setLoadingOrg] = useState(true);

  const [searchParams] = useSearchParams();
  const orgId = searchParams.get("orgId");

  const navigate = useNavigate();

  const { t } = useTranslation();

  // Fetch organization info on mount
  useEffect(() => {
    if (!orgId) {
      // Si no hay orgId pero sí hay DEFAULT_ORGANIZATION_ID, redirigir
      if (DEFAULT_ORGANIZATION_ID) {
        navigate(`/signup?orgId=${DEFAULT_ORGANIZATION_ID}`, { replace: true });
        return;
      }
      setLoadingOrg(false);
      return;
    }

    const fetchOrganization = async () => {
      try {
        const response = await axios.get(`${API_URL}/v1/auth/signup?orgId=${orgId}`);
        setOrganization(response.data);
      } catch (error: any) {
        // Don't set message here, we'll show a full view instead
      } finally {
        setLoadingOrg(false);
      }
    };

    fetchOrganization();
  }, [orgId, navigate]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    if (!orgId) {
      setMessage("Organization ID is required");
      return;
    }

    setLoading(true);
    const endpoint = "/v1/auth/signup";
    const payload = { username, email, password, organization_id: orgId };
    try {
      const response = await axios.post(API_URL + endpoint, payload);
      setMessage(response.data.message);
      if (response.data.token) {
        localStorage.setItem("token", response.data.token);
      }
      toast.success(t("user-created-succesfully-please-login"));
      navigate("/login");
    } catch (error: any) {
      console.log(error);

      setMessage(
        error.response?.data?.detail ||
          error.response?.data?.email ||
          error.response?.data?.error ||
          error.response?.data?.organization_id?.[0] ||
          "An error occurred"
      );
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    // Only show toast for API errors during submit, not for missing orgId
    if (message && orgId) {
      toast.error(message);
    }
  }, [message, orgId]);

  if (loadingOrg) {
    return (
      <div className="signup-component">
        <SimpleForm>
          <h2 className="simple-form-title">Loading...</h2>
        </SimpleForm>
      </div>
    );
  }

  // Si no hay orgId, mostrar vista completa de error
  if (!orgId) {
    return (
      <div className="signup-component">
        <SimpleForm>
          <h2 className="simple-form-title">Sign Up</h2>
          <div style={{ 
            padding: "2rem", 
            textAlign: "center",
            color: "#666"
          }}>
            <p style={{ fontSize: "1.2rem", marginBottom: "1rem" }}>
              Organization ID is required
            </p>
            <p>
              Please use a valid signup link with an organization ID to register.
            </p>
          </div>
        </SimpleForm>
      </div>
    );
  }

  // Si hay error cargando la organización, también mostrar vista completa
  if (!loadingOrg && !organization && orgId) {
    return (
      <div className="signup-component">
        <SimpleForm>
          <h2 className="simple-form-title">Sign Up</h2>
          <div style={{ 
            padding: "2rem", 
            textAlign: "center",
            color: "#666"
          }}>
            <p style={{ fontSize: "1.2rem", marginBottom: "1rem" }}>
              Organization not found
            </p>
            <p>
              The organization with the provided ID does not exist. Please use a valid signup link.
            </p>
          </div>
        </SimpleForm>
      </div>
    );
  }

  return (
    <div className="signup-component">
      <SimpleForm>
        <h2 className="simple-form-title">Sign Up</h2>

        {organization && (
          <div
            className="organization-info"
            style={{
              marginBottom: "1rem",
              padding: "1rem",
              background: "#f0f0f0",
              borderRadius: "4px",
            }}
          >
            <h3 style={{ margin: "0 0 0.5rem 0" }}>Joining: {organization.name}</h3>
            {organization.description && (
              <p style={{ margin: 0, color: "#666" }}>{organization.description}</p>
            )}
          </div>
        )}

        <form onSubmit={handleSubmit}>
          <div className="simple-form-group">
            <input
              type="text"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              required
              name="username"
              className="simple-form-input padding-medium"
              autoComplete="username"
              placeholder="Username"
              disabled={!orgId}
            />
          </div>
          <div className="simple-form-group">
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
              name="email"
              className="simple-form-input padding-medium"
              placeholder="Email"
              autoComplete="email"
              disabled={!orgId}
            />
          </div>
          <div className="simple-form-group">
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              name="password"
              className="simple-form-input padding-medium"
              autoComplete="current-password"
              placeholder="Password"
              disabled={!orgId}
            />
          </div>
          <button
            type="submit"
            className="button w-100 bg-active padding-medium"
            disabled={loading || !orgId}
          >
            {loading ? t("loading") : t("signup")}
          </button>
        </form>
      </SimpleForm>
    </div>
  );
}
