import PlaybackControls from '../PlaybackControls'
import ForecastSlider from '../ForecastSlider'

/**
 * TimelineBar is the bottom bar that holds the forecast slider
 * and playback controls. Always visible on desktop.
 */
function TimelineBar() {
  return (
    <div
      style={{
        display: 'flex',
        alignItems: 'center',
        height: '48px',
        padding: '0 16px',
        background: '#1a1a1a',
        borderTop: '1px solid #333',
        gap: '16px',
      }}
    >
      <PlaybackControls />
      <ForecastSlider />
    </div>
  )
}

export default TimelineBar
