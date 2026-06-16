import { Link, NavLink, Route, Routes } from "react-router-dom";
import { cn } from "@/lib/utils";
import SearchPage from "@/pages/SearchPage";
import RecommendPage from "@/pages/RecommendPage";

function NavTab({ to, children }) {
  return (
    <NavLink
      to={to}
      className={({ isActive }) =>
        cn(
          "rounded-md px-3 py-1.5 text-sm font-medium transition-colors",
          isActive ? "bg-white text-slate-900 shadow-sm" : "text-slate-300 hover:text-white"
        )
      }
    >
      {children}
    </NavLink>
  );
}

export default function App() {
  return (
    <div className="min-h-screen">
      <header className="bg-slate-900 text-white">
        <div className="mx-auto flex max-w-6xl items-center justify-between px-6 py-3">
          <Link to="/" className="text-lg font-semibold">
            🚗 JESKers Car Search
          </Link>
          <nav className="flex gap-1 rounded-lg bg-slate-800 p-1">
            <NavTab to="/">Search</NavTab>
            <NavTab to="/recommend">Recommend</NavTab>
          </nav>
        </div>
      </header>

      <main className="mx-auto max-w-6xl px-6 py-6">
        <Routes>
          <Route path="/" element={<SearchPage />} />
          <Route path="/recommend" element={<RecommendPage />} />
        </Routes>
      </main>
    </div>
  );
}
