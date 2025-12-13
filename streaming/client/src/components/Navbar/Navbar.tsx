import React from "react";
// import "./Navbar.css";
import { Link, useNavigate } from "react-router-dom";
import { DEFAULT_ORGANIZATION_ID } from "../../modules/constants";

export const Navbar = () => {
  const navigate = useNavigate();

  const handleSignupClick = (e: React.MouseEvent) => {
    e.preventDefault();
    const signupUrl = DEFAULT_ORGANIZATION_ID
      ? `/signup?orgId=${DEFAULT_ORGANIZATION_ID}`
      : "/signup";
    navigate(signupUrl);
  };

  return (
    <nav
      className="d-flex justify-between bg-hovered"
      style={{ background: "#002F4D" }}
    >
      <section className="logo-container">
        <img src="assets/masscer.jpg" />
      </section>
      <section className="d-flex align-center gap-small">
        <a
          className="highlighted button bg-success text-black"
          href="#"
          onClick={handleSignupClick}
          style={{ textDecoration: "none", cursor: "pointer" }}
        >
          Signup
        </a>
        <Link className="button" to={"/login"}>
          Login
        </Link>
      </section>
    </nav>
  );
};
