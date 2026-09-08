# v2.7.2 — Header Navigation Color

- Changed the application header navigation background to `#edf0f5`.
- Changed header navigation menu text, brand text, user text, and icons to black.
- Updated the mobile hamburger/toggler to use the black icon treatment.
- Preserved the existing mobile bottom navigation styling.
- Bumped frontend cache versions to `2.7.2`.
- No database migration required.

## v2.7.0
- Complete mobile UX release covering core navigation, leads, lead details, forms, reports, dashboard responsiveness, and mobile polish.
- Added mobile bottom navigation with Home, Leads, New Lead, Reports and More/Profile access.
- Added mobile lead cards while preserving the desktop Leads table.
- Added responsive report cards, mobile filters/actions and full-screen mobile modals.
- Added mobile follow-up cards and responsive dashboard recent-lead presentation.
- Added sticky lead actions, touch-friendly controls, safe-area support, reduced-motion support, empty states and horizontal-overflow prevention.
- New Lead shortcut opens the New Lead form directly from mobile navigation.

# Changelog

## v2.6.5
- Fixed Product Performance & Sales to show converted leads that have products attached, even when an older/manual conversion has no ConversionItem records.
- Added separate Converted Leads and Sold Customers metrics to prevent confusion between lead lifecycle conversion and recorded product sales.
- Kept Units Sold and Sales Revenue authoritative from ConversionItem records for incentive calculations.
- Updated dashboard product units-sold index for the expanded report columns.
- Bumped frontend cache version to 2.6.5.

## v2.6.4
- Product report fix.


## v2.7.1
- Fixed mobile bottom navigation rendering on iOS/Safari by using static navigation markup and explicit mobile visibility/positioning.
- Added active-state handling without dynamic nav injection.
- Fixed mobile New Lead action to open the New Lead form directly.
- Bumped frontend cache version to 2.7.1.
