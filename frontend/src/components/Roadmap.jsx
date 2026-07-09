// Project roadmap — the four build phases, matching the team reference.
const PHASES = [
  {
    tag: "PHASE 1",
    title: "Framework & Storyboard",
    desc: "Project skeleton and the clickable UI storyboard.",
  },
  {
    tag: "PHASE 2",
    title: "Car Search System",
    desc: "Search by brand, model, year, price, horsepower, engine type, transmission & keywords via Elasticsearch.",
  },
  {
    tag: "PHASE 3",
    title: "Smart Recommendation",
    desc: "Natural-language preferences answered with a RAG LLM over Elasticsearch.",
  },
  {
    tag: "FINAL",
    title: "Nearby & Used Listings",
    desc: "Real listings with images, prices, locations and links — one polished web app.",
  },
];

export default function Roadmap() {
  return (
    <section className="roadmap" id="roadmap">
      <div className="shell">
        <p className="eyebrow">Build plan</p>
        <h2 className="roadmap__title">From storyboard to showroom</h2>
        <div className="roadmap__track">
          {PHASES.map((p) => (
            <div className="phase" key={p.tag}>
              <div className="phase__top">
                <span className="phase__tag mono">{p.tag}</span>
              </div>
              <h3 className="phase__title">{p.title}</h3>
              <p className="phase__desc">{p.desc}</p>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
