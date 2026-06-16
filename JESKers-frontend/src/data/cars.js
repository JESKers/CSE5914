// ---------------------------------------------------------------------------
// Mock car data for the Timebox 2 Car Search System.
//
// Every record follows the CarRecord JSON Schema defined by the team
// (see "Untitled document.docx"). When Kangjie indexes the Kaggle dataset into
// Elasticsearch and Eric wires up the API, this file is replaced by live ES
// hits — the shape stays identical, so no component changes are needed.
// ---------------------------------------------------------------------------

export const mockCars = []

export const FACETS = {
  makes: [],
  bodyClasses: [],
  transmissions: ['AUTOMATIC', 'MANUAL', 'AUTOMATED_MANUAL', 'DIRECT_DRIVE'],
  drivenWheels: [
    'front wheel drive',
    'rear wheel drive',
    'all wheel drive',
    'four wheel drive',
  ],
  engineTypes: [],
  cylinders: [],
}

export const BOUNDS = {
  price: { min: 0, max: 200000 },
  hp: { min: 0, max: 1000 },
  year: { min: 2000, max: 2025 },
}
