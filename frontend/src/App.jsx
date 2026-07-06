import { NavLink, Route, Routes } from "react-router-dom";
import { cn } from "@/lib/utils";
import SearchPage from "@/pages/SearchPage";
import RecommendPage from "@/pages/RecommendPage";
import StorePage from "@/pages/StorePage";

function Nav() {
  return (
    <header className="nav">
      <div className="shell nav__inner">
        <NavLink to="/" className="nav__brand" aria-label="JESKers home">
          <span className="nav__mark" aria-hidden="true">
            <span className="nav__needle" />
          </span>
          <span className="nav__name">
            JESKers<span className="nav__dot">.</span>
          </span>
        </NavLink>
        <nav className="nav__links">
          <NavLink to="/" end className={({ isActive }) => cn(isActive && "is-active")}>
            Search
          </NavLink>
          <NavLink to="/recommend" className={({ isActive }) => cn(isActive && "is-active")}>
            Recommend
          </NavLink>
          <NavLink to="/store" className={({ isActive }) => cn(isActive && "is-active")}>
            Buy / Rent
          </NavLink>
          <a href="#roadmap">Roadmap</a>
        </nav>
        <span className="nav__badge mono">Smart Car Search</span>
      </div>
    </header>
  );
}

function Footer() {
  return (
    <footer className="footer">
      <div className="shell footer__inner">
        <span className="footer__names">Jerry · Eric · Shangrui · Kangjie</span>
        <span className="footer__tag mono">JESKers · Smart Car Recommendation System</span>
      </div>
    </footer>
  );
}

export default function App() {
  return (
    <>
      <Nav />
      <main>
        <Routes>
          <Route path="/" element={<SearchPage />} />
          <Route path="/recommend" element={<RecommendPage />} />
          <Route path="/store" element={<StorePage />} />
        </Routes>
      </main>
      <Footer />
    </>
  );
}
