const PHASES = [
  {
    tag: 'TIMEBOX 1',
    title: 'Framework & Storyboard',
    desc: 'Project skeleton and the clickable UI storyboard. Done.',
    state: 'done',
  },
  {
    tag: 'TIMEBOX 2',
    title: 'Car Search System',
    desc: 'Search by brand, model, year, price, horsepower, engine type, transmission & keywords via Elasticsearch.',
    state: 'now',
  },
  {
    tag: 'TIMEBOX 3',
    title: 'Smart Recommendation',
    desc: 'Natural-language preferences answered with a RAG LLM over Elasticsearch.',
    state: 'next',
  },
  {
    tag: 'FINAL',
    title: 'Nearby & Used Listings',
    desc: 'Real listings with images, prices, locations and links — one polished web app.',
    state: 'next',
  },
]

export default function Roadmap() {
  return (
    <section className="roadmap" id="roadmap">
      <div className="shell">
        <p className="eyebrow">Build plan</p>
        <h2 className="roadmap__title">From storyboard to showroom</h2>
        <div className="roadmap__track">
          {PHASES.map((p) => (
            <div
              key={p.tag}
              className={`phase phase--${p.state}`}
            >
              <div className="phase__top">
                <span className="phase__tag mono">{p.tag}</span>
                {p.state === 'now' && <span className="phase__live mono">● NOW</span>}
                {p.state === 'done' && <span className="phase__done mono">✓ DONE</span>}
              </div>
              <h3 className="phase__title">{p.title}</h3>
              <p className="phase__desc">{p.desc}</p>
            </div>
          ))}
        </div>
      </div>
    </section>
  )
}
