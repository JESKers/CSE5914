import { useEffect, useState } from "react";

const CHIPS = ["Corvette", "Toyota", "GTI", "Mustang", "Telluride"];

// Hero — the page's primary search. Mirrors the team reference: eyebrow, big
// display title, sub copy, a pill search bar, and quick "try" chips. Typing
// searches live (the parent debounces); the button + Enter also submit.
export default function Hero({ value, onChange, onSearch, loading }) {
  const [text, setText] = useState(value || "");

  useEffect(() => {
    setText(value || "");
  }, [value]);

  const submit = (e) => {
    e.preventDefault();
    onSearch?.(text.trim());
  };

  const pick = (chip) => {
    setText(chip);
    onChange?.(chip);
  };

  return (
    <section className="hero" id="search">
      <div className="shell">
        <p className="eyebrow rise">Smart Car Search System</p>
        <h1 className="hero__title rise" style={{ animationDelay: "0.08s" }}>
          Find the car.
          <br />
          <span className="hero__title-accent">Search every spec.</span>
        </h1>
        <p className="hero__sub rise" style={{ animationDelay: "0.16s" }}>
          Search by brand, model, year, price, horsepower, engine type, transmission and
          keywords — powered by Elasticsearch over the full vehicle dataset.
        </p>

        <form
          className="searchbar rise"
          style={{ animationDelay: "0.24s" }}
          onSubmit={submit}
        >
          <span className="searchbar__icon" aria-hidden="true">
            ⌕
          </span>
          <input
            className="searchbar__input"
            type="text"
            value={text}
            onChange={(e) => {
              setText(e.target.value);
              onChange?.(e.target.value);
            }}
            placeholder="Search make, model or keyword — e.g. Corvette, Civic, GTI…"
            aria-label="Search cars by keyword"
          />
          <button className="searchbar__btn" type="submit" disabled={loading}>
            {loading ? "Searching…" : "Search"}
            <span className="searchbar__btn-arrow" aria-hidden="true">
              →
            </span>
          </button>
        </form>

        <div className="hero__chips rise" style={{ animationDelay: "0.32s" }}>
          <span className="hero__chips-label mono">TRY</span>
          {CHIPS.map((chip) => (
            <button key={chip} type="button" className="chip" onClick={() => pick(chip)}>
              {chip}
            </button>
          ))}
        </div>
      </div>
    </section>
  );
}
