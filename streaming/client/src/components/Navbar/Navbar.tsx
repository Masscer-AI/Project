import React from "react";
import "./Navbar.css";
import { Link } from "react-router-dom";

export const Navbar = () => {
  return (
    <nav className="navbar">
      <section className="nerko-one-regular">
        <h1>
          Masscer<strong> AI</strong>
        </h1>
      </section>
      <section>
        <Link className="highlighted button bg-active" to={"/signup"}>Signup</Link>
        <Link className="button" to={"/login"}>Login</Link>
      </section>
    </nav>
  );
};
