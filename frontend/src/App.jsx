import { Navigate, Route, Routes } from "react-router-dom";

import Layout from "./components/Layout";
import Benchmarks from "./pages/Benchmarks";
import CreateTask from "./pages/CreateTask";
import Dashboard from "./pages/Dashboard";
import ApprovalCenter from "./pages/ApprovalCenter";
import Profiles from "./pages/Profiles";
import ReviewMapping from "./pages/ReviewMapping";
import TaskDetail from "./pages/TaskDetail";

function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route index element={<Dashboard />} />
        <Route path="benchmarks" element={<Benchmarks />} />
        <Route path="approvals" element={<ApprovalCenter />} />
        <Route path="profiles" element={<Profiles />} />
        <Route path="tasks/new" element={<CreateTask />} />
        <Route path="tasks/:taskId" element={<TaskDetail />} />
        <Route
          path="tasks/:taskId/review-mapping"
          element={<ReviewMapping />}
        />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Route>
    </Routes>
  );
}

export default App;
