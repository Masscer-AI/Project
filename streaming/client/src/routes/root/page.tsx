import React from "react";

import { Landing } from "../../components/Landing/Landing";
import "./page.css";
import { Navbar } from "../../components/Navbar/Navbar";

export default function Root() {
  return (
    <main className="root-page">
      <Navbar />
      <Landing />
    </main>
  );
}
