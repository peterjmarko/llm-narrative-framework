### Settings for "Balances Report"

The calculation of Solar Fire's "balances report" (planetary dominances) utilized the default weighting system, with one key modification. Based on exploratory trials, the weights for the generational planets (Uranus, Neptune, and Pluto) were set to zero to isolate more individualized factors. The specific "weight-points" assigned were as follows:

*   **3 points:** Sun, Moon, Ascendant (Asc), Midheaven (MC)
*   **2 points:** Mercury, Venus, Mars
*   **1 point:** Jupiter, Saturn
*   **0 points:** Uranus, Neptune, Pluto

Dominance within each astrological category (e.g., elements, modes) is automatically determined by the program through a multi-step calculation:

1.  A "total score" (TS) is calculated for each division (e.g., the element 'fire', the mode 'cardinal') by summing the "weight-points" of all chart points located within it.
2.  An "average score" (AS) is then determined for the category by averaging the TS values across all its constituent divisions.
3.  Two thresholds are established using this AS and predefined ratios: a "weak threshold" (WT) calculated with a "weak ratio" (WR), and a "strong threshold" (ST) calculated with a "strong ratio" (SR):
    *   `WT = AS * WR`
    *   `ST = AS * SR`
4.  Finally, a division is classified as 'weak' if its TS was below the WT, or 'strong' if its TS was greater than or equal to the ST.

The interpretive output of this process is the resulting list of 'strong' and 'weak' classifications for each division, which is then used for profile assembly.