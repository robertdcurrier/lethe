-- lethe SQLite seed data
-- Species + signal profiles + known noise sources.
-- Kept intentionally small; extend via INSERTs.

INSERT OR IGNORE INTO species
  (id, scientific_name, common_name, notes)
VALUES
  (1, 'Tursiops truncatus', 'bottlenose dolphin',
   'Common coastal/pelagic delphinid; vocal repertoire '
   || 'includes whistles, clicks, and burst-pulse sounds.');

INSERT OR IGNORE INTO signal_profile
  (species_id, name, freq_lo, freq_hi, notes)
VALUES
  (1, 'whistle', 4000, 20000,
   'Narrow-band frequency-modulated tonal calls. '
   || 'Fundamental typically 4-16 kHz, harmonics higher.'),
  (1, 'echolocation_click', 40000, 150000,
   'Broadband biosonar clicks. Requires recording '
   || 'sr > 300 kHz to capture; 48 kHz recordings '
   || 'cannot resolve this profile.'),
  (1, 'burst_pulse', 500, 40000,
   'Stereotyped packet calls spanning a wide band; '
   || 'low-end energy extends into the ship-noise range.');

INSERT OR IGNORE INTO noise_source
  (id, name, category, freq_lo, freq_hi,
   temporal_character, notes)
VALUES
  (1, 'ship_engine', 'anthropogenic',
   30, 600, 'tonal-harmonic',
   'Diesel engine fundamental + harmonics; '
   || 'dominant below 500 Hz in vessel recordings.'),
  (2, 'propeller_cavitation', 'anthropogenic',
   100, 5000, 'broadband-modulated',
   'Broadband cavitation noise modulated at blade-rate; '
   || 'intensity depends on depth and load.'),
  (3, 'snapping_shrimp', 'biological',
   2000, 24000, 'impulsive',
   'Snaps from Alpheus spp.; dominant in '
   || 'subtropical/coastal recordings (e.g. Gulf of Mexico).'),
  (4, 'seismic_airgun', 'anthropogenic',
   10, 200, 'impulsive',
   'High-amplitude low-frequency pulses from seismic '
   || 'surveys; audible many kilometers away.'),
  (5, 'flow_noise', 'geophysical',
   1, 100, 'broadband-stationary',
   'Hydrodynamic flow over the hydrophone; dominant '
   || 'at very low frequencies during platform motion.');
