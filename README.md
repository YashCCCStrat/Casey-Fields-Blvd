# Casey Fields Boulevard – contribution plan workspace

Working repository for the **Casey Fields Boulevard Contribution Plan** (City of Casey): the plans the corridor passes
through, their maps placed on the ground, and their projects and tables as GIS layers.

Started 2026-11-13 from [YashCCCStrat/Contribution-Plans](https://github.com/YashCCCStrat/Contribution-Plans) at commit
`ad2cb2b` (that repository and its website are unchanged).

## Layout
| Folder | Contents |
|---|---|
| `sources/pdfs/` | Plan documents the corridor touches (see `sources/README.md`) |
| `gis/corridor/` | Draft corridor line and 100/250/500 m buffers, VPA precincts, DCPO/ICO overlays |
| `gis/croskell/` | Croskell (Employment) ICP: georeferenced plan maps, project and land layers, QGIS project |
| `data/reference/` | Reference tables (e.g. the 37 corridor projects from the Contribution-Plans register) |
| `data/private/` | Casey-internal data – git-ignored, never committed |
| `symbology/` | Map icons: Mapbox Maki (CC0), road signs (CC0), north arrows (CC BY-SA 2.5) |
| `tools/` | Scripts that build the layers |
| `docs/` | How it works, architecture, project log |
