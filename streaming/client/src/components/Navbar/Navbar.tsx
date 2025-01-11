import React from "react";
// import "./Navbar.css";
import { Link } from "react-router-dom";

export const Navbar = () => {
  return (
    <nav className="d-flex justify-between bg-hovered">
      <section className="logo-container">
        <img src="masscer.jpg" />
      </section>
      <section className="d-flex align-center gap-small">
        <Link
          className="highlighted button bg-success text-black"
          to={"/signup"}
        >
          Signup
        </Link>
        <Link className="button" to={"/login"}>
          Login
        </Link>
      </section>
    </nav>
  );
};
