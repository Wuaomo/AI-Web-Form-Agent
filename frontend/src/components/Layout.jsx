import { NavLink, Outlet } from "react-router-dom";

const navigation = [
  { to: "/", label: "Runs", end: true },
  { to: "/workflows", label: "Workflows" },
  { to: "/approvals", label: "Approvals" },
  { to: "/profiles", label: "Profiles" },
  { to: "/benchmarks", label: "Evaluation" },
];

function Layout() {
  return (
    <div className="app-shell">
      <header className="site-header">
        <div>
          <p className="eyebrow">Human-in-the-loop automation</p>
          <h1>AI Web Form Agent</h1>
        </div>
        <nav aria-label="Main navigation">
          {navigation.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.end}
              className={({ isActive }) => (isActive ? "active" : "")}
            >
              {item.label}
            </NavLink>
          ))}
        </nav>
      </header>

      <main className="page-container">
        <Outlet />
      </main>
    </div>
  );
}

export default Layout;
