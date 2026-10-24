import { Routes, Route } from "react-router-dom";
import Login from "./pages/Login";
import Chat from "./pages/Chat";
import Admin from "./pages/Admin";
import Security from "./pages/Security";
import Profile from "./pages/Profile";
import AuthCallback from "./pages/AuthCallback";

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<Login />} />
      <Route path="/chat" element={<Chat />} />
      <Route path="/admin" element={<Admin />} />
      <Route path="/security" element={<Security />} />
      <Route path="/profile" element={<Profile />} />
      <Route path="/auth/callback" element={<AuthCallback />} />
    </Routes>
  );
}