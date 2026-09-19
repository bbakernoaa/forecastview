import { useCallback, useEffect, useMemo, useState } from 'react'
import ProductSelector from './components/ProductSelector'
import ForecastMap from './components/ForecastMap'
import FillImageLayer from './components/FillImageLayer'
import IsolineLayer from './components/IsolineLayer'
import ContourLabelLayer from './components/ContourLabelLayer'
import MapStyleSelector from './components/MapStyleSelector'
import RenderingSelector from './components/RenderingSelector'
import type { RenderingMode } from './components/RenderingSelector'
import ContourIntervalSelector from './components/ContourIntervalSelector'
import OpacitySlider from './components/OpacitySlider'
import ConnectionStatus from './components/ConnectionStatus'
import ExportButton from './components/ExportButton'
import IngestButton from './components/IngestButton'
import NotificationArea from './components/NotificationArea'
import DateSelector from './components/DateSelector'
import RunSelector from './components/RunSelector'
import VariableSelector from './components/VariableSelector'
import LevelSelector from './components/LevelSelector'
import LayerPanel from './components/LayerPanel'
import MapInspector from './components/MapInspector'
import SmartSearch from './components/SmartSearch'
import Toolbar from './components/layout/Toolbar'
import TimeDisplayBar from './components/layout/TimeDisplayBar'
import LeftPanel from './components/layout/LeftPanel'
import RightPanel from './components/layout/RightPanel'
import TimelineBar from './components/layout/TimelineBar'
import MobileHeader from './components/layout/MobileHeader'
import type { MobileTab } from './components/layout/MobileHeader'
import MobileDrawer from './components/layout/MobileDrawer'
import { useResponsive } from './hooks/useResponsive'
import { useLocalStorage } from './hooks/useLocalStorage'
import { useVariables, useTimes } from './hooks/useMetadata'
import { useUrlState } from './hooks/useUrlState'
import { usePrefetch } from './hooks/usePrefetch'
import { ViewerProvider, useViewer } from './context/ViewerContext'
import { NotificationProvider } from './context/NotificationContext'
import { DEFAULT_MAP_STYLE, MAP_STYLES } from './config/mapStyles'
import type { MapStyleKey } from './config/mapStyles'
import './App.css'

const STORAGE_KEY = 'forecastview:mapStyle'

function isValidMapStyleKey(value: unknown): value is MapStyleKey {
  return typeof value === 'string' && value in MAP_STYLES
}

function AppContent() {
  const { state, dispatch, map, setMap, playing } = useViewer()
  const { product, date, run, variable, level, forecastHour, renderingMode, contourInterval } = state
  const [fillOpacity, setFillOpacity] = useState(0.7)
  const [mobileTab, setMobileTab] = useState<MobileTab>(null)

  const { isMobile } = useResponsive()

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

  // Auto-select first forecast hour if current is not in the available list
  useEffect(() => {
    if (forecastHours.length > 0 && !forecastHours.includes(forecastHour)) {
      dispatch({ type: 'SET_FORECAST_HOUR', payload: forecastHours[0] })
    }
  }, [forecastHours, forecastHour, dispatch])

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

  // Handlers
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

  const defaultContourInterval = useMemo(() => {
    return selectedVariableInfo?.rendering?.contourInterval ?? null
  }, [selectedVariableInfo])

  const currentInfo = useMemo(() => ({
    variableName: selectedVariableInfo?.shortName || selectedVariableInfo?.fullName || variable,
    fhrLabel: `F${String(forecastHour).padStart(3, '0')}`,
  }), [selectedVariableInfo, variable, forecastHour])

  return (
    <div id="app">
      {isMobile ? (
        <MobileHeader
          activeTab={mobileTab}
          onToggleTab={setMobileTab}
          currentInfo={currentInfo}
        />
      ) : (
        <Toolbar>
          <SmartSearch />
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
          <ExportButton />
          <IngestButton />
          <ConnectionStatus />
        </Toolbar>
      )}

      <TimeDisplayBar />
      <NotificationArea />

      <div className="main-content">
        {!isMobile && (
          <LeftPanel variable={selectedVariableInfo}>
            <LayerPanel map={map} />
          </LeftPanel>
        )}

        <div className="map-area">
          <ForecastMap styleKey={mapStyle} onMapReady={setMap} />
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

        {!isMobile && <RightPanel />}
      </div>

      {isMobile && mobileTab && (
        <MobileDrawer activeTab={mobileTab} onClose={() => setMobileTab(null)}>
          {mobileTab === 'search' && (
            <SmartSearch onSelectResult={() => setMobileTab(null)} placeholder="Search species, region..." />
          )}

          {mobileTab === 'controls' && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
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
              <LayerPanel map={map} />
              <div style={{ display: 'flex', gap: '8px', marginTop: '8px' }}>
                <ExportButton />
                <IngestButton />
              </div>
            </div>
          )}

          {mobileTab === 'legend' && (
            <LeftPanel variable={selectedVariableInfo}>
              <LayerPanel map={map} />
            </LeftPanel>
          )}

          {mobileTab === 'inspector' && <MapInspector />}
        </MobileDrawer>
      )}

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
