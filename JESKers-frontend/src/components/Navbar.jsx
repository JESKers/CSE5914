import { motion } from 'framer-motion'

export default function Navbar() {
  return (
    <motion.header
      className="nav"
      initial={{ y: -24, opacity: 0 }}
      animate={{ y: 0, opacity: 1 }}
      transition={{ duration: 0.5, ease: [0.16, 1, 0.3, 1] }}
    >
      <div className="shell nav__inner">
        <a className="nav__brand" href="#top">
          <span className="nav__mark" aria-hidden="true">
            <span className="nav__needle" />
          </span>
          <span className="nav__name">
            JESKers<span className="nav__dot">.</span>
          </span>
        </a>

        <nav className="nav__links">
          <a href="#search">Search</a>
          <a href="#results">Results</a>
          <a href="#roadmap">Roadmap</a>
        </nav>

        <span className="nav__badge mono">CSE 5914 · TIMEBOX 2</span>
      </div>
    </motion.header>
  )
}
