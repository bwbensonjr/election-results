# Big Board Application 

Basic specification of a Big Board application artifact to follow results on election night.

# Functionality

- The primary view of the Big Board application is a U.S. map with modes for office
  - For 2026 the offices are Governor, Senate, and House
- The map has boundaries for the different offices and allows for
  zooming and selecting to see details for the identified race.
- The metric that drives the color of the districts on the map can
  configured and by default will use shades of blue and red, or grey
  for unknown/missing
  - Metrics for 2026
    - Party of incumbent
    - Harris/Trump margin
    - Polling average
    - Election night results
- When a district is selected it should show the full details for the
  district and the current election night results if any.
  - Details for 2026
    - Incumbent
    - Winner, if called 
    - Election night results (votes/vote percent, percent reporting)
    - Harris/Trump Margin
    - PVI 

# Design Factors 

- Should the UI be driven off of flat files or a SQLite database?
- Most of the data is locked before election night, but the results
  data will be updated every several minutes (probably 5 or 10
  minutes) based on a script that makes a web URL requests to
  the established AP API endpoint.
- The ingestor has not been written for 2026, but the endpoint we are
  planning on using is described in
  [`election-endpoints.md`](../2026/results/election-endpoints.md).
