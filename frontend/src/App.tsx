import { useCallback, useMemo, useState } from 'react'
import ProductSelector from './components/ProductSelector'
import ForecastMap from './components/ForecastMap'
import BoundsLayer from './components/BoundsLayer'
import PreviewLayer from './components/PreviewLayer'
import FillImageLayer from './components/FillImageLayer'
import IsolineLayer from './components/IsolineLayer'
import ContourLabelLayer from './components/ContourLabelLayer'
import MapStyleSelector from './components/MapStyleSelector'
import RenderingSelector from './components/RenderingSelector'
import type { RenderingMode } from './components/RenderingSelector'
import ContourIntervalSelector from './components/ContourIntervalSelector'
import OpacitySlider from './components/OpacitySlider'
import ConnectionStatus from './components/ConnectionStatus'
import NotificationArea from './components/NotificationArea'
import DateSelector from './components/DateSelector'
import RunSelector from './components/RunSelector'
import VariableSelector from './components/VariableSelector'
import LevelSelector from './components/LevelSelector'
import LayerPanel from './components/LayerPanel'
import Toolbar from './components/layout/Toolbar'
import TimeDisplayBar from './components/layout/TimeDisplayBar'
import LeftPanel from './components/layout/LeftPanel'
import RightPanel from './components/layout/RightPanel'
import TimelineBar from './components/layout/TimelineBar'
import { useLocalStorage } from './hooks/useLocalStorage'
import { useVariables, useTimes } from './hooks/useMetadata'
import { useUrlState } from './hooks/useUrlState'
import { usePrefetch } from './hooks/usePrefetch'
import { ViewerProvider, useViewer } from './context/ViewerContext'
import { NotificationProvider } from './context/NotificationContext'
import { DEFAULT_MAP_STYLE, MAP_STYLES } from './config/mapStyles'
import type { MapStyleKey } from './config/mapStyles'

const STORAGE_KEY = 'forecastview:mapStyle'

function isValidMapStyleKey(value: unknown): value is MapStyleKey {
  return typeof value === 'string' && value in MAP_STYLES
}

function AppContent() {
  const { state, dispatch, map, setMap, playing } = useViewer()
  const { product, date, run, variable, level, forecastHour, renderingMode, contourInterval } = state
  const [fillOpacity, setFillOpacity] = useState(0.7)

  // Sync viewer state ↔ URL query parameters
  useUrlState(state, dispatch)

  const [mapStyle, setMapStyle] = useLocalStorage<MapStyleKey>(
    STORAGE_KEY,
    DEFAULT_MAP_STYLE,
    isValidMapStyleKey
  )

  // Fetch variables for the current product/date/run to get full VariableInfo
  const { data: variablesList } = useVariables(product, date, run)

  // Fetch forecast hours for prefetch
  const { data: timesData } = useTimes(product, date, run)
  const forecastHours = useMemo(() => {
    if (!timesData) return []
    return timesData.forecastHours.map((entry) => entry.fhr)
  }, [timesData])

  // Prefetch neighboring forecast hours (fhr±1) for smooth animation
  usePrefetch({
    currentFhr: forecastHour,
    forecastHours,
    product,
    date,
    run,
    variable,
    level,
    interval: contourInterval,
    playing,
  })

  // Derive the full VariableInfo object for the selected variable name
  const selectedVariableInfo = useMemo(() => {
    if (!variable || !variablesList) return null
    return variablesList.find((v) => v.name === variable) ?? null
  }, [variable, variablesList])

  // Dispatch-based handlers for selectors
  const handleProductChange = useCallback((newProduct: string) => {
    dispatch({ type: 'SET_PRODUCT', payload: newProduct })
  }, [dispatch])

  const handleDateChange = useCallback((newDate: string) => {
    dispatch({ type: 'SET_DATE', payload: newDate })
  }, [dispatch])

  const handleRunChange = useCallback((newRun: string) => {
    dispatch({ type: 'SET_RUN', payload: newRun })
  }, [dispatch])

  const handleVariableChange = useCallback((newVariable: string) => {
    dispatch({ type: 'SET_VARIABLE', payload: newVariable })
  }, [dispatch])

  const handleLevelChange = useCallback((newLevel: number) => {
    dispatch({ type: 'SET_LEVEL', payload: newLevel })
  }, [dispatch])

  const handleRenderingChange = useCallback((mode: RenderingMode) => {
    dispatch({ type: 'SET_RENDERING_MODE', payload: mode })
  }, [dispatch])

  const handleContourIntervalChange = useCallback((interval: number | null) => {
    dispatch({ type: 'SET_CONTOUR_INTERVAL', payload: interval })
  }, [dispatch])

  // Derive the default contour interval from the selected variable's config
  const defaultContourInterval = useMemo(() => {
    return selectedVariableInfo?.rendering?.contourInterval ?? null
  }, [selectedVariableInfo])

  return (
    <div id="app">
      <Toolbar>
        <ProductSelector product={product} onChange={handleProductChange} />
        <DateSelector
          product={product}
          selectedDate={date}
          onDateChange={handleDateChange}
        />
        <RunSelector
          product={product}
          date={date}
          selectedRun={run}
          onRunChange={handleRunChange}
        />
        <VariableSelector
          product={product}
          date={date}
          run={run}
          selectedVariable={variable}
          onVariableChange={handleVariableChange}
        />
        <LevelSelector
          product={product}
          date={date}
          run={run}
          variable={variable}
          selectedLevel={level}
          onLevelChange={handleLevelChange}
        />
        <RenderingSelector mode={renderingMode} onChange={handleRenderingChange} />
        <ContourIntervalSelector
          defaultInterval={defaultContourInterval}
          interval={contourInterval}
          onChange={handleContourIntervalChange}
        />
        <OpacitySlider value={fillOpacity} onChange={setFillOpacity} />
        <MapStyleSelector styleKey={mapStyle} onChange={setMapStyle} />
        <ConnectionStatus />
      </Toolbar>
      <TimeDisplayBar />
      <NotificationArea />
      <div className="main-content">
        <LeftPanel variable={selectedVariableInfo}>
          <LayerPanel map={map} />
        </LeftPanel>
        <div className="map-area">
          <ForecastMap styleKey={mapStyle} onMapReady={setMap} />
          {/* { /* Dev-only layers disabled for production
          <BoundsLayer
            map={map}
            product={product}
            date={date}
            run={run}
          />
          <PreviewLayer
            map={map}
            product={product}
            date={date}
            run={run}
            variable={variable}
          />
          */ }
          <FillImageLayer
            map={map}
            product={product}
            date={date}
            run={run}
            variable={variable}
            level={level}
            fhr={forecastHour}
            visible={renderingMode === 'filled' || renderingMode === 'filled+contours'}
            opacity={fillOpacity}
          />
          <IsolineLayer
            map={map}
            product={product}
            date={date}
            run={run}
            variable={variable}
            level={level}
            fhr={forecastHour}
            interval={contourInterval}
            visible={renderingMode === 'contours' || renderingMode === 'filled+contours'}
          />
          <ContourLabelLayer
            map={map}
            visible={renderingMode === 'contours' || renderingMode === 'filled+contours'}
          />
        </div>
        <RightPanel />
      </div>
      <TimelineBar />
    </div>
  )
}

function App() {
  return (
    <NotificationProvider>
      <ViewerProvider>
        <AppContent />
      </ViewerProvider>
    </NotificationProvider>
  )
}

export default App
