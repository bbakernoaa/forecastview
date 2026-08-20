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
  product: string
  date: string | null
  run: string | null
  variable: string | null
  level: number | null
  forecastHour: number
  renderingMode: RenderingMode
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
        forecastHour: 0,
      }
    case 'SET_RUN':
      return {
        ...state,
        run: action.payload,
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
  map: MaplibreMap | null
  setMap: (map: MaplibreMap | null) => void
  /** Whether animation playback is active */
  playing: boolean
  /** Set animation playing state (called by PlaybackControls) */
  setPlaying: (playing: boolean) => void
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
  initialState?: Partial<ViewerState>
}

export function ViewerProvider({ children, initialState }: ViewerProviderProps) {
  const [state, dispatch] = useReducer(viewerReducer, {
    ...INITIAL_STATE,
    ...initialState,
  })

  const [map, setMapRaw] = useState<MaplibreMap | null>(null)
  const [playing, setPlaying] = useState(false)

  const setMap = useCallback((m: MaplibreMap | null) => {
    setMapRaw(m)
  }, [])

  const value = useMemo<ViewerContextValue>(
    () => ({ state, dispatch, map, setMap, playing, setPlaying }),
    [state, dispatch, map, setMap, playing],
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
