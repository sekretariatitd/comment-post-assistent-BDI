import { Navigate, Route, Routes } from "react-router";

import { Layout } from "./components/Layout";
import { ProtectedRoute } from "./components/ProtectedRoute";
import Activity from "./pages/Activity";
import Login from "./pages/Login";
import Posts from "./pages/Posts";
import ReviewQueue from "./pages/ReviewQueue";
import Settings from "./pages/Settings";
import Sources from "./pages/Sources";
import Templates from "./pages/Templates";

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route element={<ProtectedRoute />}>
        <Route element={<Layout />}>
          <Route index element={<Navigate to="/queue" replace />} />
          <Route path="/queue" element={<ReviewQueue />} />
          <Route path="/posts" element={<Posts />} />
          <Route path="/sources" element={<Sources />} />
          <Route path="/templates" element={<Templates />} />
          <Route path="/activity" element={<Activity />} />
          <Route path="/settings" element={<Settings />} />
          <Route path="*" element={<Navigate to="/queue" replace />} />
        </Route>
      </Route>
    </Routes>
  );
}
