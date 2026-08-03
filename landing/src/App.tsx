import { Navigate, Route, Routes } from "react-router-dom";
import { HomePage } from "./HomePage";
import { LegalPage } from "./LegalPage";

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<HomePage />} />
      <Route path="/privacy" element={<LegalPage docId="privacy" />} />
      <Route path="/terms" element={<LegalPage docId="terms" />} />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
