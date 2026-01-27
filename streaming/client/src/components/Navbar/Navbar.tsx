import React from "react";
import { Link, useNavigate } from "react-router-dom";
import { DEFAULT_ORGANIZATION_ID } from "../../modules/constants";
import styles from "./Navbar.module.css";

/** Logo: replace `streaming/client/public/assets/masscer.jpg` with your image,
 *  or change the `src` below to another path (e.g. `assets/your-logo.png`). */
const LOGO_SRC = "assets/masscer.jpg";

export const Navbar = () => {
  const navigate = useNavigate();

  const handleSignupClick = () => {
    const signupUrl = DEFAULT_ORGANIZATION_ID
      ? `/signup?orgId=${DEFAULT_ORGANIZATION_ID}`
      : "/signup";
    navigate(signupUrl);
  };

  return (
    <nav className={styles.nav}>
      <Link to="/" className={styles.logoLink} aria-label="Masscer home">
        <img
          src={LOGO_SRC}
          alt="Masscer"
          className={styles.logo}
        />
      </Link>
      <div className={styles.actions}>
        <button
          type="button"
          className={`${styles.btn} ${styles.btnPrimary}`}
          onClick={handleSignupClick}
        >
          Signup
        </button>
        <Link to="/login" className={`${styles.btn} ${styles.btnSecondary}`}>
          Login
        </Link>
      </div>
    </nav>
  );
};
