"""Aksara Kala | Can Rp20,000 skins reach the Year 3 sales target?

Run from PowerShell in the folder containing this file:
    py -m pip install numpy matplotlib
    py aksara_kala_monte_carlo.py
    py aksara_kala_monte_carlo.py sensitivity --downloads 200000
    py aksara_kala_monte_carlo.py monte-carlo --runs 20000 --seed 42

The default command runs the 2027–2029 financial projection and saves a PNG.
    py aksara_kala_monte_carlo.py projection --monthly-csv monthly.csv
Legacy commands "both", "sensitivity" and "monte-carlo" retain their earlier assumptions.
Part 1 documents inputs. Part 2 tracks activity, ownership and monthly purchases.
Part 3 shows the 36-month uncertainty bands. Part 4 evaluates nine fixed cases.
Part 5 prints the target gap and writes the graphs. Sources follow the code.

How to read the results
    Buyers = distinct people making their first purchase in the reporting period.
    Units = all skins sold, including repeat and second-item purchases.
    Gross revenue = units x skin price, before fees, artist shares and costs.
    The target applies to months 25-36. Cumulative totals include all 36 months.
    The fixed cases have no probability weights. Monte Carlo percentiles depend
    on the assumed input ranges and distribution choices.
"""

import argparse
from pathlib import Path

import numpy as np


# %% Part 1 | What inputs drive the outcome?
# Planning assumptions. Each range is (low, most likely, high).
# These are illustrative inputs. Replace them with estimates from your own data.
DOWNLOADS_OVER_3_YEARS = (20_000, 60_000, 120_000)
DOWNLOAD_SHARE_BY_YEAR = (0.20, 0.30, 0.50)
FIRST_PLAY_RATE = (0.50, 0.70, 0.85)  # First-time players per download.
MONTHLY_RETENTION = (0.15, 0.50, 0.70)  # Active last month and active this month.
MONTHLY_REACTIVATION = (0.005, 0.015, 0.035)  # Per lapsed player per month.
MONTHLY_SHOP_REACH = (0.25, 0.65, 0.80)  # Saw the offer per active player.
FIRST_PURCHASE_RATE = (0.002, 0.05, 0.08)  # Per exposed non-buyer in a drop month.
REPEAT_PURCHASE_RATE = (0.03, 0.15, 0.25)  # Per exposed owner with skins left to buy.
SECOND_SKIN_RATE = (0.02, 0.05, 0.10)  # Per buyer with 2+ unowned skins that month.
BETWEEN_DROP_MULTIPLIER = 0.50  # First and repeat purchase rates relative to drop months.

# Each skin has a small buff. Calibrate the purchase rates above with
# playtest data for this price and buff.
SKIN_PRICE_IDR = 20_000  # Product choice and deck interview [1].
YEAR_3_GROSS_TARGET = 400_000_000  # Annual ambition from the deck [1].
# Release schedule used by the middle case.
MONTHS_PER_YEAR = 12
YEARS = 3
MONTHS = MONTHS_PER_YEAR * YEARS
LAUNCH_SKINS = 4
SKINS_PER_DROP = 1
MONTHS_BETWEEN_DROPS = 2
PERCENTILES = (10, 50, 90)


# %% Part 2 | How do downloads become sales?
# Downloads represent distinct new installs. Within a year they arrive evenly.
# Each run holds its sampled rates constant. Input ranges are independent.
# Buffs, art and artist support are bundled into the conversion assumptions.
def draw_range(rng, bounds, size):
    low, most_likely, high = bounds
    if low == high:
        return np.full(size, low)
    return rng.triangular(low, most_likely, high, size=size)


def yearly_totals(monthly_counts):
    return monthly_counts.reshape(-1, YEARS, MONTHS_PER_YEAR).sum(axis=2)


def update_ownership(active, catalog, orders, second_skins):
    """Move each purchaser one group to the right, or two for a two-skin order."""
    active[..., :catalog] -= orders
    active[..., 1:catalog + 1] += orders
    active[..., 1:catalog] -= second_skins
    active[..., 2:catalog + 1] += second_skins


def simulate(runs, seed, downloads, launch_skins, skins_per_drop, drop_every, *, monthly=False):
    """Return yearly buyer and sales counts by default, or monthly counts on request."""
    rng = np.random.default_rng(seed)

    # Draw each rate once per simulated future, then sample events monthly.
    download_totals = np.rint(
        draw_range(rng, DOWNLOADS_OVER_3_YEARS, runs)
    ).astype(np.int64)
    if downloads is not None:
        download_totals.fill(downloads)

    first_play_rate = draw_range(rng, FIRST_PLAY_RATE, runs)
    retention = draw_range(rng, MONTHLY_RETENTION, runs)[:, None]
    reactivation = draw_range(rng, MONTHLY_REACTIVATION, runs)[:, None]
    shop_reach = draw_range(rng, MONTHLY_SHOP_REACH, runs)[:, None]
    first_purchase = draw_range(rng, FIRST_PURCHASE_RATE, runs)
    repeat_purchase = draw_range(rng, REPEAT_PURCHASE_RATE, runs)[:, None]
    second_skin_rate = draw_range(rng, SECOND_SKIN_RATE, runs)[:, None]

    # Spread each year's downloads across its months. Cumulative rounding
    # preserves each run's original three-year total.
    monthly_shares = np.repeat(DOWNLOAD_SHARE_BY_YEAR, MONTHS_PER_YEAR)
    cumulative_share = np.cumsum(monthly_shares) / MONTHS_PER_YEAR
    cumulative_share[-1] = 1.0
    cumulative_downloads = np.rint(
        download_totals[:, None] * cumulative_share
    ).astype(np.int64)
    monthly_downloads = np.diff(cumulative_downloads, axis=1, prepend=0)

    # Month 1 is launch. For a 3-month cadence the next drop is in month 4.
    drops = np.zeros(MONTHS, dtype=np.int64)
    drops[0] = launch_skins
    drops[drop_every::drop_every] = skins_per_drop
    catalog_by_month = drops.cumsum()

    # Each column is a group of players with the same number of owned skins.
    # Keeping dormant players in these groups preserves past purchases.
    active = np.zeros((runs, int(catalog_by_month[-1]) + 1), dtype=np.int64)
    dormant = np.zeros_like(active)
    first_plays = np.zeros(runs, dtype=np.int64)
    buyers = np.zeros((runs, MONTHS), dtype=np.int64)
    sales = np.zeros_like(buyers)

    for month, catalog_size in enumerate(catalog_by_month):
        returning = rng.binomial(active, retention)
        reactivated = rng.binomial(dormant, reactivation)
        dormant += active - returning - reactivated
        active = returning + reactivated

        new_players = rng.binomial(monthly_downloads[:, month], first_play_rate)
        active[:, 0] += new_players
        first_plays += new_players

        # Only players who still have something they can buy enter this draw.
        eligible_active = active[:, :catalog_size]
        exposed = rng.binomial(eligible_active, shop_reach)
        month_multiplier = 1.0 if drops[month] else BETWEEN_DROP_MULTIPLIER
        orders = np.empty_like(exposed)
        orders[:, 0] = rng.binomial(exposed[:, 0], first_purchase * month_multiplier)
        orders[:, 1:] = rng.binomial(exposed[:, 1:], repeat_purchase * month_multiplier)

        # All orders include one new skin. Some buyers add a second if they
        # have at least two unowned skins. The whole catalog stays on sale.
        second_skins = rng.binomial(orders[:, :-1], second_skin_rate)
        update_ownership(active, catalog_size, orders, second_skins)

        buyers[:, month] = orders[:, 0]
        sales[:, month] = orders.sum(axis=1) + second_skins.sum(axis=1)

    if not monthly:
        buyers = yearly_totals(buyers)
        sales = yearly_totals(sales)
    return download_totals, first_plays, buyers, sales, catalog_by_month


# %% Part 3 | How wide is the range across simulated futures?
def print_row(label, values, prefix=""):
    percentiles = np.percentile(values, PERCENTILES)
    columns = [f"{prefix}{value:,.0f}" for value in percentiles]
    print(f"{label:<23} {columns[0]:>15} {columns[1]:>15} {columns[2]:>15}")


def save_plot(path, monthly_buyers, monthly_sales, catalog):
    from matplotlib.backends.backend_agg import FigureCanvasAgg
    from matplotlib.figure import Figure
    from matplotlib.ticker import StrMethodFormatter

    # Sum within each simulation before taking percentiles across simulations.
    buyers = np.percentile(monthly_buyers.cumsum(axis=1), PERCENTILES, axis=0)
    sales = np.percentile(monthly_sales.cumsum(axis=1), PERCENTILES, axis=0)
    revenue_millions = sales * (SKIN_PRICE_IDR / 1_000_000)
    months = np.arange(MONTHS + 1)
    metrics = (
        ("Unique buyers", buyers, True, "#4D3294"),
        ("Skins sold", sales, True, "#006D6F"),
        ("Gross revenue (Rp million)", revenue_millions, False, "#9A4C12"),
    )

    figure = Figure(figsize=(9.5, 8), facecolor="white")
    FigureCanvasAgg(figure)
    axes = figure.subplots(len(metrics), sharex=True)
    figure.subplots_adjust(left=0.13, right=0.95, bottom=0.12, top=0.79, hspace=0.42)
    figure.text(0.13, 0.95, "Cumulative skin sales over three years", fontsize=22, weight="bold", color="#211837")
    figure.text(
        0.13,
        0.91,
        f"{monthly_buyers.shape[0]:,} simulations  |  Rp{SKIN_PRICE_IDR:,} per skin"
        f"  |  {catalog[0]} skins at launch, {catalog[-1]} by month {MONTHS}",
        fontsize=10,
        color="#565065",
    )
    for axis, (title, percentiles, count_axis, color) in zip(axes, metrics):
        low, median, high = np.pad(percentiles, ((0, 0), (1, 0)))
        axis.fill_between(months, low, high, color=color, alpha=0.17, label="P10–P90 range")
        axis.plot(months, median, color=color, linewidth=2.4, label="Median (P50)")
        axis.set_title(title, loc="left", fontsize=12, weight="bold", color="#211837")
        axis.set_ylim(0, max(1 if count_axis else 0.10, high[-1] * 1.10))
        axis.set_xlim(0, MONTHS)
        tick_format = "{x:,.0f}" if count_axis else "{x:,.2f}"
        axis.yaxis.set_major_formatter(StrMethodFormatter(tick_format))
        axis.locator_params(axis="y", nbins=4, integer=count_axis)
        axis.grid(axis="y", color="#E8E5ED", linewidth=0.8)
        axis.set_axisbelow(True)
        for boundary in range(MONTHS_PER_YEAR, MONTHS, MONTHS_PER_YEAR):
            axis.axvline(boundary, color="#C8C3D1", linestyle="--", linewidth=0.8)
        axis.spines[["top", "right", "left"]].set_visible(False)
        axis.spines["bottom"].set_color("#D8D3E0")
        axis.tick_params(colors="#565065", length=0, labelsize=9, pad=6)

    band, line = axes[0].get_legend_handles_labels()[0]
    figure.legend(
        handles=[line, band],
        loc="upper left",
        bbox_to_anchor=(0.12, 0.885),
        ncol=2,
        frameon=False,
        fontsize=9,
    )
    axes[-1].set_xticks(np.arange(0, MONTHS + 1, 6))
    axes[-1].set_xlabel("Months since launch", color="#565065", labelpad=8)
    figure.text(0.13, 0.027, "Source: Aksara Kala model. Bands show the middle 80% of runs at each month.", fontsize=9, color="#565065")
    figure.savefig(path, dpi=160)


# %% Part 4 | Which assumptions move Year 3 revenue?
def project_skin_sales(downloads, shop_reach, first_purchase_rate,
                       launch_skins, skins_per_drop, drop_every):
    """Return expected first-time buyers and skin sales for each year."""

    # Use the middle planning estimate for inputs outside the sensitivity grid.
    first_play_rate = FIRST_PLAY_RATE[1]
    retention = MONTHLY_RETENTION[1]
    reactivation = MONTHLY_REACTIVATION[1]
    repeat_rate = REPEAT_PURCHASE_RATE[1]
    second_skin_rate = SECOND_SKIN_RATE[1]

    # Group players by how many skins they own. Index 0 means never bought.
    final_catalog = launch_skins + ((MONTHS - 1) // drop_every) * skins_per_drop
    active = np.zeros(final_catalog + 1)
    dormant = np.zeros_like(active)
    monthly = np.zeros((MONTHS, 2))

    for month in range(MONTHS):
        year = month // MONTHS_PER_YEAR
        catalog = launch_skins + (month // drop_every) * skins_per_drop

        # Add new players and bring back some active and dormant players.
        new_downloads = downloads * DOWNLOAD_SHARE_BY_YEAR[year] / MONTHS_PER_YEAR
        returning = active * retention
        reactivated = dormant * reactivation
        dormant += active - returning - reactivated
        active = returning + reactivated
        active[0] += new_downloads * first_play_rate

        # Owners who already have the entire catalog cannot buy another skin.
        # The first group uses the first-purchase rate. Owners use the repeat rate.
        eligible_viewers = active[:catalog] * shop_reach
        purchase_rates = np.full(catalog, repeat_rate, dtype=float)
        purchase_rates[0] = first_purchase_rate
        if month % drop_every != 0:
            purchase_rates *= BETWEEN_DROP_MULTIPLIER
        orders = eligible_viewers * purchase_rates

        # Some buyers add a second skin if they still have two available.
        second_skins = orders[:-1] * second_skin_rate

        # Move buyers to their new ownership groups so they count as first-time
        # buyers only once, even if they stop playing and later return.
        update_ownership(active, catalog, orders, second_skins)

        monthly[month, 0] = orders[0]
        monthly[month, 1] = orders.sum() + second_skins.sum()

    # Keep fractional expected counts during the calculation. Round in the output.
    return monthly.reshape(YEARS, MONTHS_PER_YEAR, 2).sum(axis=1)





def report_monte_carlo(args, path):
    downloads, first_plays, monthly_buyers, monthly_sales, catalog = simulate(
        args.runs, args.seed, args.downloads, args.launch_skins, args.skins_per_drop, args.drop_every,
        monthly=True,
    )
    buyers = yearly_totals(monthly_buyers)
    sales = yearly_totals(monthly_sales)

    print(f"Aksara Kala | {args.runs:,} simulations | seed {args.seed}")
    print(f"Skin price: Rp{SKIN_PRICE_IDR:,} | {catalog[0]} skins at launch | {catalog[-1]} by month 36")
    print("Planning scenarios based on editable assumptions.")
    print("P10, P50, and P90 are the 10th percentile, median, and 90th percentile.")

    print(f"\n{'Three-year total':<23} {'P10':>15} {'P50':>15} {'P90':>15}")
    print_row("Downloads", downloads)
    print_row("First-time players", first_plays)
    print_row("Unique skin buyers", buyers.sum(axis=1))
    print_row("Skins sold", sales.sum(axis=1))
    print_row("Gross skin revenue", sales.sum(axis=1) * SKIN_PRICE_IDR, prefix="Rp")

    for year in range(YEARS):
        print(f"\nYear {year + 1}")
        print_row("First-time skin buyers", buyers[:, year])
        print_row("Skins sold", sales[:, year])
        print_row("Gross skin revenue", sales[:, year] * SKIN_PRICE_IDR, prefix="Rp")

    save_plot(path, monthly_buyers, monthly_sales, catalog)
    print(f"Saved graph to {path.resolve()}")


def report_sensitivity(args, path):
    """Cross three shop-reach values with three drop-month first-purchase rates."""
    import matplotlib.pyplot as plt

    downloads = DOWNLOADS_OVER_3_YEARS[1] if args.downloads is None else args.downloads
    schedule = (args.launch_skins, args.skins_per_drop, args.drop_every)
    revenue_grid = np.empty((len(MONTHLY_SHOP_REACH), len(FIRST_PURCHASE_RATE)))
    print("\nYear 3 gross revenue (Rp million)")
    print("Shop reach   " + "  ".join(f"{rate:>8.2%}" for rate in FIRST_PURCHASE_RATE))
    for row, reach in enumerate(MONTHLY_SHOP_REACH):
        for col, rate in enumerate(FIRST_PURCHASE_RATE):
            annual = project_skin_sales(downloads, reach, rate, *schedule)
            revenue_grid[row, col] = annual[-1, 1] * SKIN_PRICE_IDR / 1_000_000
            if row == 1 and col == 1:
                middle = annual
        print(f"{reach:>9.0%}    " + "  ".join(f"{v:>8.2f}" for v in revenue_grid[row]))

    # Units are expected counts. Keep their full precision for revenue calculations.
    print("\nMiddle case                 New buyers    Units sold     Gross (Rp)")
    for index, (buyers, units) in enumerate(middle, start=1):
        print(f"Year {index:<23}{buyers:>10,.0f}    {units:>10,.0f}    {units * SKIN_PRICE_IDR:>12,.0f}")
    buyers, units = middle.sum(axis=0)
    print(f"Three years                 {buyers:>10,.0f}    {units:>10,.0f}    {units * SKIN_PRICE_IDR:>12,.0f}")
    required = (args.target_gross + SKIN_PRICE_IDR - 1) // SKIN_PRICE_IDR
    gap = max(0, required - middle[-1, 1])
    print(f"Year 3 target: {required:,} sales | Middle-case shortfall: {gap:,.0f} sales")

    # Left: people versus units in each year, so repeat buying is visible.
    # Right: change two inputs while keeping downloads, price and schedule fixed.
    fig, (bars, heat) = plt.subplots(1, 2, figsize=(12, 5.8))
    fig.subplots_adjust(left=.08, right=.97, top=.76, bottom=.25, wspace=.40)
    fig.suptitle("What drives Year 3 skin revenue?", x=.08, ha="left", fontsize=21, weight="bold")
    fig.text(.08, .865, f"{downloads:,} three-year downloads   |   Rp{SKIN_PRICE_IDR:,} per skin"
             f"   |   {args.launch_skins} at launch, then {args.skins_per_drop} every {args.drop_every} months")
    years = np.arange(1, YEARS + 1)
    bars.bar(years - .18, middle[:, 0], .36, label="First-time buyers", color="#5946A1")
    bars.bar(years + .18, middle[:, 1], .36, label="Skins sold", color="#168582")
    bars.set(xticks=years, xlabel="Year", ylabel="Expected count", title="Annual sales in the middle case")
    bars.legend(frameon=False)
    bars.spines[["top", "right"]].set_visible(False)

    heat.imshow(revenue_grid, cmap="Purples", aspect="auto", vmin=0, vmax=max(revenue_grid.max(), .01))
    heat.set_xticks(range(len(FIRST_PURCHASE_RATE)), [f"{v:.2%}" for v in FIRST_PURCHASE_RATE])
    heat.set_yticks(range(len(MONTHLY_SHOP_REACH)), [f"{v:.0%}" for v in MONTHLY_SHOP_REACH])
    heat.set(xlabel="First-purchase rate among eligible viewers in a drop month",
             ylabel="Monthly shop reach", title="Year 3 gross revenue (Rp million)")
    for (row, col), value in np.ndenumerate(revenue_grid):
        heat.text(col, row, f"{value:,.2f}", ha="center", va="center", fontsize=13,
                  color="white" if value > .55 * revenue_grid.max() else "#252137")
    fig.text(.08, .117, f"Year 3 target: Rp{args.target_gross:,} gross  |  {required:,} skins needed"
             f"  |  Middle case: {middle[-1, 1]:,.0f} skins")
    fig.text(.08, .06, "Sources: BudayaGo pp. 12-13 (price and target); project assumptions (purchase and activity rates).",
             fontsize=9, color="#565065")
    fig.savefig(path, dpi=160)
    plt.close(fig)
    print(f"Saved graph to {path.resolve()}")


# %% Part 5 | Run the analysis and export the charts
# %% Three-year financial projection | January 2027 through December 2029
# Use "projection" for the final financial case. The sensitivity and Monte Carlo
# commands above retain their historical rate ranges and drop-month conventions.
# Change the named inputs here to rerun the final projection locally.
from csv import DictWriter
from datetime import date
from math import ceil, prod

PLAN_DOWNLOADS = 200_000
PLAN_FIRST_PURCHASE = 0.05        # Every month, per exposed eligible never-buyer.
ARTIST_SHARE = 0.30              # Both shares are fractions of gross billings.
PLATFORM_SHARE = 0.10
BASE_OPEX = (61_000_000, 118_000_000, 188_000_000)
DECK_GROSS = (30_000_000, 215_000_000, 400_000_000)
BUDAYAGO_Y1_SHARE = 0.12        # Within Year 1 downloads; shifts timing only.
LAUNCH_WEIGHTS = (0.60, 0.30, 0.10)
EID_CAMPAIGN_MONTH = (3, 2, 2)  # One campaign month per year, later dates provisional.
SCENARIOS = {"No campaigns": None, "Half reach lift": 0.5, "Campaign plan": 1.0,
             "Higher reach lift": 1.5}
# Each lift is the share reached among active players still missed by other
# placements. Costs are extra spend ABOVE the canvas operating budget, in IDR.
# Format: channel, reach fraction, cash cost, placement and cost timing.
CHANNELS = (
    ("BudayaGo launch", 0.12, 1_200_000, "Partner coverage and trackable QR link; cost once at launch."),
    ("Ramadan / Lebaran", 0.20, 450_000, "Opt-in cultural quest and artist collection in the Eid month; cost per event."),
    ("Independence Day", 0.15, 300_000, "August community quest with a shop preview; cost per event."),
    ("National Batik Day", 0.25, 350_000, "October artisan showcase with a tagged collection; cost per event."),
    ("Wardrobe preview", 0.12, 400_000, "Optional try-on from month 2 onward; build cost once in month 2."),
    ("Artist / guild spotlight", 0.10, 100_000, "Feature the artist in the guild feed each skin release; cost per feature."),
)


def campaign_calendar(launch, per_drop, interval):
    """Return 36 months of deliverables, activation weights and billed occurrences."""
    calendar = []
    catalog = 0
    for t in range(MONTHS):
        y, m = divmod(t, 12)
        drop = launch if t == 0 else (per_drop if t % interval == 0 else 0)
        catalog += drop
        flags = [((1, 0.5, 0.25)[t] if t < 3 else 0),
                 int(m + 1 == EID_CAMPAIGN_MONTH[y]), int(m == 7), int(m == 9),
                 int(t >= 1), int(drop > 0)]
        billed = [int(t == 0), *flags[1:4], int(t == 1), flags[5]]
        calendar.append(dict(period=date(2027 + y, m + 1, 1).isoformat(), year=y,
                             drop=drop, catalog=catalog, flags=flags, billed=billed,
                             launch_weight=LAUNCH_WEIGHTS[t] if t < 3 else 0))
    return calendar


def project_finances(downloads, calendar, lift_scale):
    """Deterministic expected counts. Ownership carries across active and lapsed months."""
    active = np.zeros(calendar[-1]["catalog"] + 1)
    dormant = np.zeros_like(active)
    rows = []
    enabled = lift_scale is not None
    for month in calendar:
        y, catalog = month["year"], month["catalog"]
        annual_installs = downloads * DOWNLOAD_SHARE_BY_YEAR[y]
        partner_pool = annual_installs * BUDAYAGO_Y1_SHARE if enabled and y == 0 else 0
        partner_installs = partner_pool * month["launch_weight"]
        installs = (annual_installs - partner_pool) / 12 + partner_installs
        new = installs * FIRST_PLAY_RATE[1]

        retained = active * MONTHLY_RETENTION[1]
        returned = dormant * MONTHLY_REACTIVATION[1]
        dormant += active - retained - returned
        active = retained + returned
        active[0] += new
        active_total = active.sum()

        # Channel rates apply sequentially to the remaining unreached group.
        missed = prod(1 - min(1, rate * flag * (lift_scale or 0))
                      for (_, rate, _, _), flag in zip(CHANNELS, month["flags"]))
        reach = 1 - (1 - MONTHLY_SHOP_REACH[1]) * missed
        spend = sum(c[2] * flag for c, flag in zip(CHANNELS, month["billed"])) if enabled else 0
        viewers = active[:catalog] * reach
        repeat_rate = REPEAT_PURCHASE_RATE[1] * (1 if month["drop"] else BETWEEN_DROP_MULTIPLIER)
        orders = viewers * repeat_rate
        orders[0] = viewers[0] * PLAN_FIRST_PURCHASE
        extra = orders[:-1] * SECOND_SKIN_RATE[1]
        units = orders.sum() + extra.sum()
        gross = units * SKIN_PRICE_IDR
        artist, platform = gross * ARTIST_SHARE, gross * PLATFORM_SHARE
        studio = gross - artist - platform
        opex = BASE_OPEX[y] / 12
        update_ownership(active, catalog, orders, extra)
        rows.append(dict(month=month["period"], partner=partner_installs, downloads=installs,
                         first_plays=new, retained=retained.sum(), returned=returned.sum(),
                         active=active_total, reach=reach, viewers=active_total * reach,
                         first_viewers=viewers[0], owner_viewers=viewers[1:].sum(),
                         first_buyers=orders[0], repeat_orders=orders[1:].sum(),
                         second_units=extra.sum(), units=units, gross=gross, artist=artist,
                         platform=platform, studio=studio, base_opex=opex, campaigns=spend,
                         operating=studio - opex - spend))
    return rows


def annual_finances(rows):
    """Flows sum across months. Reach is weighted by active player-months."""
    annual = []
    for start in range(0, len(rows), 12):
        year = rows[start:start + 12]
        total = {key: sum(r[key] for r in year) for key in year[0] if key not in ("month", "reach")}
        total["reach"] = total["viewers"] / total["active"] if total["active"] else 0
        annual.append(total)
    return annual


def report_projection(args):
    """Print the paired financial cases, reconcile changes, export a chart and optional CSV."""
    from matplotlib import pyplot as plt

    n = PLAN_DOWNLOADS if args.downloads is None else args.downloads
    schedule = (args.launch_skins, args.skins_per_drop, args.drop_every)
    calendar = campaign_calendar(*schedule)
    results = {name: project_finances(n, calendar, scale) for name, scale in SCENARIOS.items()}
    totals = {name: annual_finances(rows) for name, rows in results.items()}
    annual = totals["Campaign plan"]
    old = project_skin_sales(n, MONTHLY_SHOP_REACH[1], FIRST_PURCHASE_RATE[1], *schedule)
    print(f"Financial projection | {n:,} downloads | Rp{SKIN_PRICE_IDR:,} per skin")
    print(f"First purchases: {PLAN_FIRST_PURCHASE:.1%} of exposed never-buyers each month.")
    print("                                Year 1         Year 2         Year 3        3 years")
    for key, label in (("first_buyers", "New buyers"), ("units", "Skins sold"), ("gross", "Gross sales"),
                       ("artist", "Artist payout"), ("platform", "Platform fees"), ("studio", "Studio proceeds"),
                       ("base_opex", "Base operating costs"), ("campaigns", "Extra campaign spend"),
                       ("operating", "Operating result")):
        values = [y[key] for y in annual]
        print(f"{label:<23}" + "".join(f"{v:>15,.0f}" for v in [*values, sum(values)]))
    print("\nYear 3 gross revenue by case (Rp):")
    print(f"{'Previous drop-adjusted run':<28} {old[-1, 1] * SKIN_PRICE_IDR:>14,.0f}")
    for name, years in totals.items():
        print(f"{name:<28} {years[-1]['gross']:>14,.0f}")
    gap = args.target_gross - annual[-1]["gross"]
    print(f"Year 3 gross target less forecast: Rp{gap:,.0f}")
    studio_per_skin = SKIN_PRICE_IDR * (1 - ARTIST_SHARE - PLATFORM_SHARE)
    target_units = ceil(args.target_gross / SKIN_PRICE_IDR)
    break_even = ceil((annual[-1]["base_opex"] + annual[-1]["campaigns"]) / studio_per_skin)
    control = totals["No campaigns"][-1]
    print(f"Year 3 target: {target_units:,} skins | target less forecast: {target_units - annual[-1]['units']:,.0f}")
    print(f"Year 3 operating break-even: {break_even:,} skins")
    print(f"Year 3 active players seeing the shop: {annual[-1]['reach']:.1%}")
    print(f"Year 3 additional gross vs no campaigns: Rp{annual[-1]['gross'] - control['gross']:,.0f}")
    print(f"Year 3 additional operating profit vs no campaigns: Rp{annual[-1]['operating'] - control['operating']:,.0f}")
    if args.monthly_csv:
        with args.monthly_csv.open("w", newline="", encoding="utf-8-sig") as output:
            writer = DictWriter(output, fieldnames=["scenario", *results["Campaign plan"][0]])
            writer.writeheader()
            for name, rows in results.items():
                writer.writerows(dict(scenario=name, **row) for row in rows)
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.6), layout="constrained")
    for name, color in (("No campaigns", "#92869c"), ("Campaign plan", "#6d3064")):
        axes[0].plot(range(1, 37), [r["reach"] * 100 for r in results[name]], color=color, label=name)
    axes[0].set(xlabel="Month since launch", ylabel="Active players reached (%)", ylim=(0, 100))
    axes[0].legend(frameon=False)
    for name, values, color in (
        ("Pitch target", [*DECK_GROSS[:2], args.target_gross], "#ad731d"),
        ("Campaign plan", [r["gross"] for r in annual], "#6d3064"),
        ("No campaigns", [r["gross"] for r in totals["No campaigns"]], "#92869c")):
        axes[1].plot([1, 2, 3], np.array(values) / 1e6, marker="o", label=name, color=color)
    axes[1].set(xticks=[1, 2, 3], xlabel="Projection year", ylabel="Gross sales (Rp million)", ylim=(0, None))
    axes[1].legend(frameon=False)
    fig.suptitle("Aksara Kala  |  Shop reach and gross skin sales")
    path = args.plot or Path("aksara_kala_financial_projection.png")
    fig.savefig(path, dpi=160)
    plt.close(fig)
    print(f"Saved graph to {path.resolve()}")

# Additional research for the financial case: Indonesia's Cabinet Secretariat,
# national holiday decree for 2027; later Eid months are planning windows.
# https://setkab.go.id/en/govt-annnounces-2027-national-holidays-and-collective-leave-days/
# https://www.islamiccal.com/en/gregorian-calendar/indonesia/2028/
# https://www.islamiccal.com/pdf/hijri/en-indonesia-1450.pdf
# October artist programming: Indonesian Ministry of Foreign Affairs, National Batik Day.
# https://kemlu.go.id/washington/berita/indonesia-celebrates-national-batik-day-at-the-world-bank-headquarters-in-washington-dc?type=publication
# Attribution design: https://partner.steamgames.com/doc/marketing/utm_analytics
# All campaign reach, install timing and cost inputs are planning estimates. Test
# exposure on a player-level holdout. Log acquisition source, first play, unique
# shop impression, receipt and owned skin IDs. Report each channel's coverage of
# previously unreached players and incremental studio proceeds less campaign spend.
# P&L is before tax and financing, uses gross billings before fees and excludes
# grants, refunds and VAT adjustments. All years use the canvas artist/platform
# split and operating budgets. A binding contract or channel fee overrides them.


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("mode", choices=["projection", "both", "sensitivity", "monte-carlo"], nargs="?", default="projection")
    parser.add_argument("--downloads", type=int, help="Fixed new downloads over all 36 months")
    parser.add_argument("--target-gross", type=int, default=YEAR_3_GROSS_TARGET)
    parser.add_argument("--runs", type=int, default=20_000)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--launch-skins", type=int, default=LAUNCH_SKINS)
    parser.add_argument("--skins-per-drop", type=int, default=SKINS_PER_DROP)
    parser.add_argument("--drop-every", type=int, default=MONTHS_BETWEEN_DROPS)
    parser.add_argument("--plot", nargs="?", const=None, type=Path, metavar="PNG",
                        help="Custom PNG path. In both mode the second path gets a _sensitivity suffix.")
    parser.add_argument("--monthly-csv", type=Path, help="Export all four financial cases in projection mode")
    args = parser.parse_args()
    if min(args.launch_skins, args.skins_per_drop, args.drop_every, args.runs) < 1:
        parser.error("Release counts, interval and simulation runs must be positive.")
    if min(args.target_gross, args.seed) < 0 or (args.downloads is not None and args.downloads < 0):
        parser.error("Downloads, target and seed must be non-negative.")
    if args.plot and args.plot.suffix.lower() != ".png":
        parser.error("Choose a PNG filename for --plot.")

    if args.mode == "projection":
        report_projection(args)
        return

    forecast_path = args.plot or Path("aksara_kala_forecast.png")
    sensitivity_path = Path("aksara_kala_sensitivity.png")
    if args.plot:
        sensitivity_path = args.plot
        if args.mode == "both":
            sensitivity_path = args.plot.with_stem(args.plot.stem + "_sensitivity")
    if args.mode in ("both", "sensitivity"):
        report_sensitivity(args, sensitivity_path)
    if args.mode in ("both", "monte-carlo"):
        report_monte_carlo(args, forecast_path)


# %% Sources and interpretation
# [1] BudayaGo.pdf, slides 12-13 (project deck). One interview supports testing
# Rp20,000. Rp400m is the annual Year 3 gross target. The project team's revised
# offer adds a small buff. The deck's 5% and two purchases are target assumptions.
# [2] Sifa et al. (2015), Predicting Purchase Decisions in Mobile Free-to-Play
# Games. Supports modeling payer incidence and transaction counts separately.
# https://cdn.aaai.org/ojs/12788/12788-52-16305-1-2-20201228.pdf
# [3] AppsFlyer, Q3 2026 gaming benchmarks, paid media cohorts. Indonesia Android
# Action: 0.44%; RPG: 2.33% made any purchase within 30 days of installing.
# Our first-purchase denominator is exposed non-buyers in a PC game's drop month.
# https://www.appsflyer.com/blog/measurement-analytics/gaming-app-market-benchmarks-q3/
# [4] Local price context: Citampi Stories lists a Rp5,000 costume. Banyu Lintar
# Angin lists a Rp28,999 Deluxe DLC. These sources document asking prices.
# https://apps.apple.com/id/app/citampi-stories-love-and-life/id1462710484
# https://steamdb.info/sub/224641/info/
# [5] Presentation reference: KarinaMaharani/TikTok-Regional-Case, simulation.ipynb.
# The case notebook organizes inputs, comparisons, charts and limitations around
# decisions. This game's forecast uses its own inputs and monthly ownership model.
# https://github.com/KarinaMaharani/TikTok-Regional-Case/blob/main/simulation.ipynb
#
# Calibration: record first purchases / exposed non-buyers, and repeat purchases
# by distinct buyers / exposed eligible owners in the same month. Count visits by
# distinct players. Measure drop and off-month rates separately and validate on
# a later release. No causal uplift from the buff has been measured.
# Model scope: constant buff and price, no discounting, refunds or production
# costs; persistent catalog, at most two different skins per player per month.


if __name__ == "__main__":
    main()
