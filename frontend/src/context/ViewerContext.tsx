import {
  createContext,
  useContext,
  useReducer,
  useState,
  useCallback,
  useMemo,
} from 'react'
import type { ReactNode, Dispatch } from 'react'
import type { Map as MaplibreMap } from 'maplibre-gl'
import type { RenderingMode } from '../components/RenderingSelector'

// --------------------------------------------------------------------------
// State Interface
// --------------------------------------------------------------------------

export interface ViewerState {
  /** Active product identifier */
  product: string
  /** Selected date in YYYYMMDD format, or null if none selected */
  date: string | null
  /** Selected initialization run (e.g. "00", "06"), or null */
  run: string | null
  /** Selected variable name, or null */
  variable: string | null
  /** Selected vertical level value, or null */
  level: number | null
  /** Current forecast hour */
  forecastHour: number
  /** Active rendering mode */
  renderingMode: RenderingMode
  /** User-overridden contour interval (null = use variable default) */
  contourInterval: number | null
}

// --------------------------------------------------------------------------
// Action Types
// --------------------------------------------------------------------------

export type ViewerAction =
  | { type: 'SET_PRODUCT'; payload: string }
  | { type: 'SET_DATE'; payload: string }
  | { type: 'SET_RUN'; payload: string }
  | { type: 'SET_VARIABLE'; payload: string }
  | { type: 'SET_LEVEL'; payload: number }
  | { type: 'SET_FORECAST_HOUR'; payload: number }
  | { type: 'SET_RENDERING_MODE'; payload: RenderingMode }
  | { type: 'SET_CONTOUR_INTERVAL'; payload: number | null }

// --------------------------------------------------------------------------
// Reducer
// --------------------------------------------------------------------------

export function viewerReducer(state: ViewerState, action: ViewerAction): ViewerState {
  switch (action.type) {
    case 'SET_PRODUCT':
      return {
        ...state,
        product: action.payload,
        date: null,
        run: null,
        variable: null,
        level: null,
        forecastHour: 0,
      }
    case 'SET_DATE':
      return {
        ...state,
        date: action.payload,
        run: null,
        variable: null,
        level: null,
        forecastHour: 0,
      }
    case 'SET_RUN':
      return {
        ...state,
        run: action.payload,
        variable: null,
        level: null,
        forecastHour: 0,
      }
    case 'SET_VARIABLE':
      return {
        ...state,
        variable: action.payload,
        level: null,
        contourInterval: null,
      }
    case 'SET_LEVEL':
      return {
        ...state,
        level: action.payload,
      }
    case 'SET_FORECAST_HOUR':
      return {
        ...state,
        forecastHour: action.payload,
      }
    case 'SET_RENDERING_MODE':
      return {
        ...state,
        renderingMode: action.payload,
      }
    case 'SET_CONTOUR_INTERVAL':
      return {
        ...state,
        contourInterval: action.payload,
      }
    default:
      return state
  }
}

// --------------------------------------------------------------------------
// Context
// --------------------------------------------------------------------------

export interface ViewerContextValue {
  state: ViewerState
  dispatch: Dispatch<ViewerAction>
  /** MapLibre map instance (managed separately from reducer) */
  map: MaplibreMap | null
  /** Set the MapLibre map instance */
  setMap: (map: MaplibreMap | null) => void
}

const ViewerContext = createContext<ViewerContextValue | null>(null)

// --------------------------------------------------------------------------
// Provider
// --------------------------------------------------------------------------

const INITIAL_STATE: ViewerState = {
  product: 'air',
  date: null,
  run: null,
  variable: null,
  level: null,
  forecastHour: 0,
  renderingMode: 'filled+contours',
  contourInterval: null,
}

interface ViewerProviderProps {
  children: ReactNode
  /** Override the initial state (useful for testing) */
  initialState?: Partial<ViewerState>
}

export function ViewerProvider({ children, initialState }: ViewerProviderProps) {
  const [state, dispatch] = useReducer(viewerReducer, {
    ...INITIAL_STATE,
    ...initialState,
  })

  // Map instance is kept as separate state — it's a ref-like value
  // that doesn't belong in the reducer (not serializable, not part of app logic)
  const [map, setMapRaw] = useState<MaplibreMap | null>(null)

  const setMap = useCallback((m: MaplibreMap | null) => {
    setMapRaw(m)
  }, [])

  const value = useMemo<ViewerContextValue>(
    () => ({ state, dispatch, map, setMap }),
    [state, dispatch, map, setMap],
  )

  return (
    <ViewerContext.Provider value={value}>
      {children}
    </ViewerContext.Provider>
  )
}

// --------------------------------------------------------------------------
// Consumer Hook
// --------------------------------------------------------------------------

export function useViewer(): ViewerContextValue {
  const ctx = useContext(ViewerContext)
  if (!ctx) {
    throw new Error('useViewer must be used within a ViewerProvider')
  }
  return ctx
}
