# Requirements Document

## Project Description (Input)
`web.display_refresh` is defined in `config.py` and served by `/api/config` as `appConfig.web.display_refresh`, but the Web UI's `configureAutoRefresh()` (`web_assets.py`) never reads it -- it hardcodes `"60"` as the Display/Kiosk auto-refresh interval fallback instead. This is dead configuration: a user cannot change the Display/Kiosk auto-refresh interval by setting `web.display_refresh`, contrary to what the config key's existence implies. Verified live: `/api/config` correctly reports a configured `display_refresh` value, but the JS function that should consume it does not.

## Requirements

### Requirement 1: Display/Kiosk auto-refresh honors the configured interval
**Objective:** As an operator running a kiosk/display-mode Web UI, I want `web.display_refresh` to actually control the auto-refresh interval, so that I don't have to rely on the undocumented, unconfigurable hardcoded default.

#### Acceptance Criteria
1. When Display or Kiosk mode is active and no `?refresh=` URL parameter overrides it, `configureAutoRefresh()` shall use `appConfig.web.display_refresh` as the refresh interval in seconds.
2. When `appConfig.web.display_refresh` is absent or falsy, the interval shall fall back to `60`, preserving existing default behavior for configurations that don't set the key.
3. The existing `?refresh=` URL parameter override shall continue to take precedence over the configured default, unchanged.
