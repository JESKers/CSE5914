import { useEffect, useState } from "react";
import SearchPage from "@/pages/SearchPage";
import RecommendPage from "@/pages/RecommendPage";
import StorePage from "@/pages/StorePage";
import AssistantPage from "@/pages/AssistantPage";

const PAGES = {
  "/": SearchPage,
  "/recommend": RecommendPage,
  "/store": StorePage,
  "/assistant": AssistantPage,
};

function AppLink({ to, currentPath, className = "", children, ...props }) {
  const active = currentPath === to;
  return (
    <a
      href={to}
      className={`${className} ${active ? "is-active" : ""}`.trim()}
      onClick={(event) => {
        if (
          event.defaultPrevented ||
          event.button !== 0 ||
          event.metaKey ||
          event.ctrlKey ||
          event.shiftKey ||
          event.altKey
        ) {
          return;
        }
        event.preventDefault();
        window.history.pushState({}, "", to);
        window.dispatchEvent(new PopStateEvent("popstate"));
      }}
      {...props}
    >
      {children}
    </a>
  );
}

function Nav({ currentPath }) {
  return (
    <header className="nav">
      <div className="shell nav__inner">
        <AppLink to="/" currentPath={currentPath} className="nav__brand" aria-label="JESKers home">
          <span className="nav__mark" aria-hidden="true">
            <span className="nav__needle" />
          </span>
          <span className="nav__name">
            JESKers<span className="nav__dot">.</span>
          </span>
        </AppLink>
        <nav className="nav__links">
          <AppLink to="/" currentPath={currentPath}>
            Search
          </AppLink>
          <AppLink to="/assistant" currentPath={currentPath}>
            Assistant
          </AppLink>
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
  const [currentPath, setCurrentPath] = useState(window.location.pathname);

  useEffect(() => {
    const syncPath = () => setCurrentPath(window.location.pathname);
    window.addEventListener("popstate", syncPath);
    return () => window.removeEventListener("popstate", syncPath);
  }, []);

  const Page = PAGES[currentPath] ?? SearchPage;
  return (
    <>
      <Nav currentPath={currentPath} />
      <main>
        <Page />
      </main>
      <Footer />
    </>
  );
}
