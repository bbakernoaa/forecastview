/**
 * TypeScript interfaces for the Forecast Viewer metadata API responses.
 *
 * These mirror the Pydantic models in backend/app/api/metadata.py.
 */

// --------------------------------------------------------------------------
// Variable & Level metadata
// --------------------------------------------------------------------------

export interface VariableRenderingInfo {
  colormap: string;
  contourInterval: number;
  fillLevels: number[];
  colors?: string[];
}

export interface VariableInfo {
  name: string;
  shortName: string;
  fullName: string;
  units: string;
  category: string;
  rendering: VariableRenderingInfo | null;
}

export interface LevelInfo {
  surfaceType: number | null;
  value: number;
  label: string;
}

export interface ForecastHourEntry {
  fhr: number;
  valid_time: string;
}

// --------------------------------------------------------------------------
// API response envelopes
// --------------------------------------------------------------------------

export interface DatesResponse {
  product: string;
  dates: string[];
}

export interface RunsResponse {
  product: string;
  date: string;
  runs: string[];
}

export interface VariablesResponse {
  product: string;
  date: string;
  run: string;
  variables: VariableInfo[];
}

export interface LevelsResponse {
  product: string;
  date: string;
  run: string;
  variable: string;
  levels: LevelInfo[];
}

export interface TimesResponse {
  product: string;
  date: string;
  run: string;
  init_time: string;
  forecast_hours: ForecastHourEntry[];
}

// --------------------------------------------------------------------------
// Filled contour API types
// --------------------------------------------------------------------------

export interface FilledMetadata {
  variable: string;
  level: number | null;
  fhr: number;
  fillLevels: number[];
  colors?: string[];
  fieldMin: number;
  fieldMax: number;
  numBands: number;
  numFeatures: number;
}

export interface FilledFeature {
  type: 'Feature';
  geometry: {
    type: 'Polygon' | 'MultiPolygon';
    coordinates: number[][][] | number[][][][];
  };
  properties: {
    level_low: number;
    level_high: number;
    [key: string]: unknown;
  };
}

export interface FilledFeatureCollection {
  type: 'FeatureCollection';
  features: FilledFeature[];
  metadata: FilledMetadata;
}

// --------------------------------------------------------------------------
// Contour API types
// --------------------------------------------------------------------------

export interface ContourMetadata {
  variable: string;
  level: number | null;
  fhr: number;
  contourInterval: number | null;
  majorInterval: number | null;
  fieldMin: number;
  fieldMax: number;
  numLevels: number;
  numFeatures: number;
}

export interface ContourFeature {
  type: 'Feature';
  geometry: {
    type: 'MultiLineString';
    coordinates: number[][][];
  };
  properties: {
    value: number;
    major: boolean;
    [key: string]: unknown;
  };
}

export interface ContourFeatureCollection {
  type: 'FeatureCollection';
  features: ContourFeature[];
  metadata: ContourMetadata;
}

// --------------------------------------------------------------------------
// Point Query API types
// --------------------------------------------------------------------------

export interface PointQueryResponse {
  lat: number
  lon: number
  variable: string
  value: number | null
  units: string
  level: number | null
  fhr: number
  valid_time: string
  grid_lat: number
  grid_lon: number
}
