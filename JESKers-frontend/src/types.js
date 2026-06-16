// ---------------------------------------------------------------------------
// Single source of truth for the data contract between the frontend and the
// backend. These JSDoc typedefs mirror the team's CarRecord JSON Schema
// (see "Untitled document.docx"). Editors pick them up for autocompletion, and
// every layer — components, API client, mock data — refers back here.
//
// If the schema changes, change it HERE first, then update cars.js and the
// backend response to match.
// ---------------------------------------------------------------------------

/**
 * @typedef {Object} Engine
 * @property {string|null} fuel_type  Engine fuel type (a.k.a. "engine type").
 * @property {number|null} hp         Horsepower; null for some EV/missing records.
 * @property {number|null} cylinders  Cylinder count; 0 for EV/rotary.
 */

/**
 * @typedef {Object} AugmentedNhtsa  Fields resolved via the NHTSA vPIC API.
 * @property {string} body_class      Standardized body class, e.g. "Coupe".
 * @property {number|null} seat_count
 * @property {string|null} [trim_level]
 */

/**
 * One vehicle record. Identical shape whether it comes from local mock data or
 * a live Elasticsearch hit, so components never need to know the source.
 *
 * @typedef {Object} CarRecord
 * @property {string} id
 * @property {string} make                 Brand, e.g. "Toyota".
 * @property {string} model                Model name, e.g. "Corvette Z06".
 * @property {number} year
 * @property {Engine} engine
 * @property {string} transmission_type    AUTOMATIC | MANUAL | AUTOMATED_MANUAL | DIRECT_DRIVE | UNKNOWN
 * @property {string} driven_wheels        front/rear/all/four wheel drive
 * @property {number|null} number_of_doors
 * @property {string[]} market_category
 * @property {number} msrp
 * @property {AugmentedNhtsa} augmented_nhtsa
 */

/**
 * The structured search criteria the UI sends. All fields optional; empty
 * arrays / null mean "no constraint".
 *
 * @typedef {Object} SearchFilters
 * @property {string} [model]            substring / prefix match
 * @property {string[]} [makes]          brand terms
 * @property {string[]} [engineTypes]    engine.fuel_type terms
 * @property {number[]} [cylinders]      engine.cylinders terms
 * @property {string[]} [transmissions]
 * @property {string[]} [drivenWheels]
 * @property {number|null} [minPrice]
 * @property {number|null} [maxPrice]
 * @property {number|null} [minHp]
 * @property {number|null} [maxHp]
 * @property {number|null} [minYear]
 * @property {number|null} [maxYear]
 */

/**
 * @typedef {Object} SearchRequest
 * @property {string} [query]            free-text keywords
 * @property {SearchFilters} [filters]
 * @property {'relevance'|'price-asc'|'price-desc'|'hp-desc'} [sort]
 * @property {number} [page]             1-based
 * @property {number} [size]             page size
 */

/**
 * What every search returns — one page of results plus the total hit count.
 * The backend MUST return this exact shape.
 *
 * @typedef {Object} SearchResponse
 * @property {CarRecord[]} results
 * @property {number} total
 * @property {number} page
 * @property {number} size
 */

export {}
