import { Routes, Route } from "react-router-dom";
import Login from "./pages/Login";
import Chat from "./pages/Chat";
import AdminLayout from "./components/AdminLayout";
import Admin from "./pages/Admin";
import AdminReset from "./pages/AdminReset";
import Security from "./pages/Security";
import Profile from "./pages/Profile";
import NewAdmins from "./pages/NewAdmins";
import AuthCallback from "./pages/AuthCallback";

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<Login />} />
      <Route path="/chat" element={<Chat />} />
      <Route path="/admin" element={<AdminLayout />}>
        <Route index element={<Admin />} />
        <Route path="reset" element={<AdminReset />} />
        <Route path="admins" element={<NewAdmins />} />
        <Route path="security" element={<Security embedded />} />
        <Route path="profile" element={<Profile embedded />} />
      </Route>
      <Route path="/security" element={<Security />} />
      <Route path="/profile" element={<Profile />} />
      <Route path="/auth/callback" element={<AuthCallback />} />
    </Routes>
  );
}