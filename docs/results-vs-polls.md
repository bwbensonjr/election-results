# Results vs. polls, 2026

How the 2026 Governor, Senate, and House results compared with the project's pre-election polling averages, and how that compares with published reviews of 2024 polling.

All 2026 figures use the checked-in AP results snapshot (`2026/results/ap-results.json`, fetched 2026-11-13 12:37 UTC) and the comparison built by `scripts/build_results_vs_polls.py`. See [Results vs. polls dataset](big-board.md#results-vs-polls-dataset) for the method and columns. Late counts can still move a few races; rerun the build against a newer snapshot to refresh these numbers.

## Method in brief

- **Miss** is the result margin minus the polling average margin, in points, for the average's two principals (the Democrat, or a reviewed independent such as Bill Hill in AK-AL, against the Republican). Positive means the Democratic side beat its polls; negative means the Republican did.
- Margins are raw shares of the total vote. Poll margins still include undecided voters, so a late break by undecided voters shows up as a miss.
- The averages are the project's weighted averages over the whole cycle, with recency decay, one question per poll, and pollster and partisan adjustments (see [district-data.md](district-data.md#house-polling-averages) and [statewide-data.md](statewide-data.md)). They are not limited to the final weeks.

## Coverage

173 of 506 races (34%) had a polling average and votes for both principals. Together the averages draw on 1,458 poll questions.

| Office | Races with an average | All races | Share | Polls |
| --- | --- | --- | --- | --- |
| Governor | 33 | 36 | 92% | 556 |
| Senate | 29 | 35 | 83% | 593 |
| House | 111 | 435 | 26% | 309 |
| Total | 173 | 506 | 34% | 1,458 |

House coverage is thin: 297 districts had no polls, 25 had no Democrat-versus-Republican field (mostly Louisiana's open primaries and uncontested seats), and 2 had polls but none naming both nominees. 95 of the 111 polled districts had four or fewer polls.

## Findings

**Democrats beat their polls in about three races out of four, by a median of 3.6 points.** The direction is the same for every office and every size of polling average.

| Group | Races | D beat polls | Median miss | Mean miss | Mean absolute miss |
| --- | --- | --- | --- | --- | --- |
| All races | 173 | 75% | D+3.6 | D+4.0 | 6.0 |
| Governor | 33 | 82% | D+3.8 | D+3.8 | 5.5 |
| Senate | 29 | 72% | D+4.0 | D+3.3 | 5.3 |
| House | 111 | 74% | D+3.4 | D+4.2 | 6.4 |
| Races with 10+ polls | 38 | 82% | D+3.4 | D+3.4 | |
| Races with 30+ polls | 13 | 100% | D+3.7 | D+4.8 | |

Weighting each race by its number of polls gives a mean of D+4.1.

**The best-polled races were the most consistent.** All 13 races with 30 or more polls went more Democratic than their average: TX-SEN (D+8.9, 75 polls), MI-SEN (D+2.6, 65), TX-GOV (D+8.9, 63), NC-SEN (D+8.4, 51), MI-GOV (D+2.2, 51), OH-SEN (D+1.6, 49), FL-GOV (D+3.0, 45), OH-GOV (D+3.7, 44), IA-SEN (D+3.7, 38), ME-SEN (D+2.7, 33), NH-SEN (D+6.3, 32), NY-GOV (D+7.5, 31), and FL-SEN (D+3.4, 30).

Median miss by number of polls in the average:

| Polls in average | Governor | Senate | House |
| --- | --- | --- | --- |
| 1 | 1 race, R+2.0 | 1 race, D+6.1 | 39 races, D+2.9 (69% D) |
| 2–4 | 4 races, D+3.9 (75% D) | 7 races, D+5.8 (71% D) | 56 races, D+4.1 (82% D) |
| 5–9 | 9 races, D+6.1 (78% D) | 4 races, D+1.9 (50% D) | 14 races, D+1.8 (57% D) |
| 10–29 | 14 races, D+3.4 (86% D) | 9 races, D+1.0 (56% D) | 2 races, D+0.9 (50% D) |
| 30+ | 5 races, D+3.7 (100% D) | 8 races, D+3.6 (100% D) | none |

**Range.** Misses ran from R+13.4 (GA-07) to D+36.3 (IL-04). Statewide races all fell between R+10.0 (SD-GOV) and D+12.7 (TN-GOV). The long tails on both sides are House districts with one to three polls.

Largest Democratic over-performance:

| Race | Polls | Result | Miss | Polls in average |
| --- | --- | --- | --- | --- |
| IL-04 | D+19.0 | D+55.3 | D+36.3 | 1 |
| CA-22 | D+9.9 | D+35.8 | D+25.8 | 2 |
| VA-06 | R+30.0 | R+10.3 | D+19.8 | 1 |
| TX-09 | R+4.2 | D+15.1 | D+19.3 | 3 |
| TX-28 | D+17.1 | D+36.1 | D+19.0 | 3 |
| TN-GOV | R+15.2 | R+2.5 | D+12.7 | 6 |
| IL-SEN | D+12.9 | D+25.3 | D+12.5 | 4 |

Largest Republican over-performance:

| Race | Polls | Result | Miss | Polls in average |
| --- | --- | --- | --- | --- |
| GA-07 | D+1.1 | R+12.4 | R+13.4 | 2 |
| GA-11 | D+2.0 | R+10.7 | R+12.7 | 1 |
| MT-02 | R+13.6 | R+25.8 | R+12.3 | 2 |
| GA-03 | R+5.0 | R+17.2 | R+12.2 | 1 |
| SD-GOV | R+17.0 | R+27.0 | R+10.0 | 5 |
| ID-SEN | R+13.8 | R+22.9 | R+9.2 | 9 |
| SD-SEN | R+12.0 | R+21.0 | R+9.0 | 15 |

Republican over-performance clustered in safe Republican states (Idaho, South Dakota, Montana) and in safe Republican House seats in Georgia.

**Caveats.**

- Races share a national environment, so the 173 misses are not independent. The pattern reads best as one systematic shift of about 3 to 4 points toward Democrats, not 173 separate errors.
- Raw margins count undecided voters in the poll margin. Some of the shift may be late deciders breaking toward Democrats rather than polls being wrong when they were taken.
- Cycle-long averages respond more slowly than final-weeks polling, so a late swing makes them miss by more.
- At the snapshot, AK-SEN and AK-AL were uncalled near 88% of the expected vote, and CA-22 was at 86%.

## Comparison with 2024

Published reviews of 2024 found a lean of about the same size in the other direction: polls overstated Democrats.

**AAPOR Task Force on 2024 Pre-Election Polling** (released October 2025):

- Across 611 polls for president, Senate, governor, and House fielded in the final two weeks, polls overstated the Democratic two-party margin by 2.7 points on average, about R+2.7 in this document's terms. The overstatement was 4.6 points in 2020 and 3.1 in 2016, so 2024 was the third straight presidential cycle in which polls underestimated Republicans.
- Midterms were close to even: polls overstated Republicans by 0.6 points in 2022 and Democrats by 0.1 in 2018. Since the 1930s, Democrats and Republicans have each been underestimated about equally often, and the same direction rarely persists for more than a couple of consecutive presidential elections.
- Polls were more accurate than in recent cycles: the average absolute error on the two-party margin was 3.3 points, against 5.3 in 2020 and 5.2 in 2016. State presidential polls missed by 3.0 points, their best for any presidential cycle since 1944.
- Causes: Republicans in Republican-leaning areas were under-represented, Hispanic support for Harris was overstated, and first-time 2024 voters, who leaned Republican, were under-counted as a share of the electorate. Turnout rose in counties that backed Trump in 2020 and fell in Biden counties, which most surveys did not anticipate; that explains a moderate share of the remaining error. The task force found no evidence of herding.

**Nate Silver, Silver Bulletin** ("So, how did the polls do in 2024? It's complicated"):

- Polls from the final three weeks showed a Democratic lean of 2.9 points across all races: about 3 points in presidential, Senate, and House polls and about 2 in governor polls. The lean was 4.7 points in 2020 and 3.0 in 2016; 2022 had a much smaller Democratic lean and 2018 a slight Republican one.
- Average error was 4.5 points, the lowest in his database (the average since 1998 is 5.9). Presidential polls missed by 3.4 points and Senate polls by 4.1, the lowest on record for the Senate.
- He notes that a consistent lean limits what averaging can fix, since most polls miss in the same direction.

| | 2024, AAPOR | 2024, Silver | 2026, this project |
| --- | --- | --- | --- |
| Direction of the typical miss | R+2.7 (mean) | R+2.9 (mean) | D+3.6 (median), D+4.0 (mean) |
| Typical size of a miss, either direction | 3.3 | 4.5 | 6.0 |
| Polls measured | Individual polls, final two weeks, two-party margin | Individual polls, final three weeks, top-two margin | Weighted averages over the cycle, raw margin |

The figures are not strictly comparable. Ours score cycle-long averages on raw margins and include many House averages built from one or two polls, all of which tend to make misses larger. The direction and rough size of the lean are clear in both years, though. A swing from about R+3 in 2024 to about D+3.5 in 2026 fits AAPOR's finding that the direction of polling misses doesn't persist, especially from a presidential year to a midterm.

## Reproducing

```sh
uv run scripts/build_results_vs_polls.py                                    # from the checked-in snapshot
uv run scripts/build_results_vs_polls.py --results 2026/live/results.json   # from a newer live file
```

The figures above come from `2026/results/results-vs-polls.csv` (rows with `status` `compared`) and `2026/results/results-vs-polls-polls.csv`. On the Big Board, the Results vs. Polls metric colors the map by these misses, and the detail panel with no race selected shows the scatter and the median-miss table for the current office.

## Sources

- AAPOR Task Force on 2024 Pre-Election Polling, [executive summary (PDF)](https://aapor.org/wp-content/uploads/2025/10/Task-Force-on-2024-Pre-Election-Polling-Report-Executive-Summary.pdf) and [full report (PDF)](https://aapor.org/wp-content/uploads/2025/10/AAPOR-Task-Force-on-2024-Pre-Election-Polling_Report.pdf), October 2025.
- Nate Silver, ["So, how did the polls do in 2024? It's complicated"](https://www.natesilver.net/p/so-how-did-the-polls-do-in-2024-its), Silver Bulletin.
- NPR, ["The polls underestimated Trump's support — again. Here's why"](https://www.npr.org/2024/11/12/nx-s1-5188445/2024-election-polls-trump-kamala-harris), November 12, 2024.
