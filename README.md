# Aksara Kala Skin Sales Forecast

Aksara Kala is a free-to-play PC action RPG that teaches Sundanese and Javanese scripts. This model estimates how many players would buy its optional Rp20,000 skins with small in-game buffs and how much the studio would earn from January 2027 through December 2029.

The main forecast uses a **monthly, deterministic model**. Given the same inputs, it produces the same expected counts and rupiah totals. It compares campaigns at a fixed **5% monthly first-purchase rate among players who see a skin offer and have never bought one**.

## Three-year results

| Campaign plan | 2027 | 2028 | 2029 | Three years |
| --- | ---: | ---: | ---: | ---: |
| Downloads | 40,000 | 60,000 | 100,000 | 200,000 |
| First-time skin buyers | 1,925 | 3,267 | 5,709 | 10,902 |
| Skins sold | 2,172 | 3,762 | 6,632 | 12,566 |
| Gross sales | Rp43.44m | Rp75.25m | Rp132.64m | Rp251.32m |
| Studio proceeds after artist and platform shares | Rp26.06m | Rp45.15m | Rp79.58m | Rp150.79m |
| Base operating costs | Rp61.00m | Rp118.00m | Rp188.00m | Rp367.00m |
| Additional campaign costs | Rp3.30m | Rp1.70m | Rp1.70m | Rp6.70m |
| Operating profit or loss | −Rp38.24m | −Rp74.55m | −Rp110.12m | −Rp222.91m |

Year 3 reaches **33.2% of the original Rp400 million annual gross target**. The gap is **Rp267.36 million**, or about **13,368 skins** at Rp20,000 each. Covering the modeled Year 3 operating and campaign costs would require **15,809 skins**, given studio proceeds of Rp12,000 per skin.

## How the calculation works

1. **Distribute installs.** The three years receive 20%, 30%, and 50% of the 200,000 projected downloads. The campaign plan allocates 12% of Year 1 installs to BudayaGo, distributed 60% in January, 30% in February, and 10% in March. The remaining installs arrive evenly across each year. The partner allocation changes launch timing within the same download total.
2. **Estimate active players.** Each month, 70% of new downloads become first-time players. The model adds 50% of the previous month's active players and 1.5% of players who were already inactive. Each player keeps their skin ownership when they become inactive or return.
3. **Estimate shop exposure.** Organic placements reach 65% of active players. Each scheduled campaign reaches a share of the players still unreached. The formula below accounts for overlap between placements.
4. **Estimate orders.** Each month, 5% of exposed players who have never bought a skin make a first purchase. Among exposed owners with skins left to buy, 15% order in release months and 7.5% order in other months. Each order starts with one skin. If two or more unowned skins are available, 5% of those orders add a second.
5. **Update the catalog and ownership.** The game starts with four skins, adds one every two months, and keeps previous skins on sale. After checkout, the model moves players to their updated ownership groups. A player contributes to first-time buyer totals once.
6. **Calculate the financial result.** Multiply skins sold by Rp20,000. Deduct 30% of gross sales for artist royalties and 10% for storefront and payment fees. Subtract base operating costs and extra campaign spend from studio proceeds. The operating result is before tax and financing.

The model keeps fractional expected counts during calculation and rounds only for display. It sums the 12 monthly results to get each annual figure. Each annual shop-reach percentage divides total monthly viewer counts by total monthly active counts, so busier months carry more weight.

## How campaigns change shop reach

| Placement | Share of remaining unreached players | Schedule | Extra budget |
| --- | ---: | --- | ---: |
| BudayaGo launch coverage | 12% at full intensity | First three months at 100%, 50%, and 25% intensity | Rp1.20m once |
| Ramadan and Lebaran collection | 20% | March 2027, February 2028 and February 2029 | Rp450k per event |
| Independence Day quest | 15% | August each year | Rp300k per event |
| National Batik Day showcase | 25% | October each year | Rp350k per event |
| Wardrobe preview | 12% | Every month from month two | Rp400k once |
| Artist showcase in the guild feed | 10% | Every skin release, including launch | Rp100k per release |

**Monthly reach = 1 − (1 − organic reach) × product of (1 − effective lift) for all placements.** Each effective lift equals the placement rate times its monthly intensity and the scenario multiplier, capped at 100%.

### Worked example from January 2027

1. **Installs** = (40,000 − 4,800) ÷ 12 + (4,800 × 60%) = **5,813.33**.
2. **Active players** = 5,813.33 × 70% = **4,069.33**. At launch, all active players are new.
3. **Shop reach** = 1 − (1 − 65%) × (1 − 12%) × (1 − 10%) = **72.28%**. BudayaGo and the artist showcase run in January.
4. **First-time buyers** = 4,069.33 × 72.28% × 5% ≈ **147.07**. The second-skin assumption adds about 7.35 units, bringing expected sales to **154.42 skins**.
5. **Gross sales** ≈ **Rp3.09m**. The studio retains **Rp1.85m** after the 40% combined share. After **Rp5.08m** in base costs and **Rp1.30m** in launch campaign costs, the operating loss is **Rp4.53m**.

## What changed from the earlier forecast?

| Year 3 scenario | Gross sales |
| --- | ---: |
| Earlier run with 5% first purchase in release months and 2.5% between releases | Rp89.42m |
| Flat 5% first purchase, without extra campaigns | Rp118.69m |
| Flat 5%, half the planned campaign reach lifts | Rp125.85m |
| Flat 5%, planned campaign reach lifts | Rp132.64m |
| Flat 5%, 1.5 times the planned campaign reach lifts | Rp139.05m |

Using 5% every month raises Year 3 gross sales by **Rp29.27m**. The campaign plan raises weighted shop reach from **65.0% to 72.3%** and adds another **Rp13.95m** in gross sales. After revenue shares and extra campaign spending, the Year 3 operating result improves by **Rp6.67m**. The three campaign cases use the same schedule and spend. Their differences reflect how many players the campaigns reach.

## Reproduce the forecast

Run these commands in PowerShell from the repository folder.

```powershell
py -m pip install numpy matplotlib
py aksara_kala_monte_carlo.py projection --downloads 200000 --plot financial_projection.png --monthly-csv financial_projection_monthly.csv
```

- [`aksara_kala_monte_carlo.py`](./aksara_kala_monte_carlo.py) prints the annual financial results and scenario comparison. The command also saves a PNG and a monthly CSV for all four projection cases.
- The Excel workbook contains the **Projection**, **Customer journey**, **Case comparison**, **Inputs**, **Calendar**, monthly model, and **Research** tabs. Start with **Inputs** to adjust assumptions in Excel. In Python, see `PLAN_FIRST_PURCHASE`, `BASE_OPEX`, and `CHANNELS` for the first-purchase rate, budget, and campaign assumptions.
- The script also supports the earlier `sensitivity` and `monte-carlo` modes, which use their own purchase-rate assumptions. Use `projection` to reproduce the figures on this page.

## Evidence and assumptions

- **Project deck and business model canvas.** The deck records one student interview supporting a test at around Rp20,000 and sets the Rp400m gross Year 3 target. The canvas supplies the operating budgets and the assumed 30% artist and 10% platform shares. The original canvas describes 200,000 active Year 3 players. This projection uses 200,000 cumulative downloads, then estimates monthly activity.
- **Purchase behavior and pricing.** Research on mobile free-to-play purchases informs the distinction between first and repeat orders. AppsFlyer benchmarks track Android installs that convert to a payer within 30 days, using a different population and measurement window than the shop-view conversion in this model. Indonesian game listings show asking prices for costumes or add-ons. [Sifa et al.](https://cdn.aaai.org/ojs/12788/12788-52-16305-1-2-20201228.pdf) · [AppsFlyer](https://www.appsflyer.com/blog/measurement-analytics/gaming-app-market-benchmarks-q3/) · [Citampi Stories](https://apps.apple.com/id/app/citampi-stories-love-and-life/id1462710484) · [Banyu Lintar Angin](https://steamdb.info/sub/224641/info/)
- **Campaign timing.** Indonesia's holiday schedule and National Batik Day inform the placement calendar. The 2028 and 2029 Lebaran months are provisional. [2027 holiday schedule](https://setkab.go.id/en/govt-annnounces-2027-national-holidays-and-collective-leave-days/) · [National Batik Day](https://kemlu.go.id/washington/berita/indonesia-celebrates-national-batik-day-at-the-world-bank-headquarters-in-washington-dc?type=publication)
- **What to measure at launch.** Downloads, 5% conversion, campaign lift, and campaign costs are planning inputs. Track tagged installs, unique shop viewers, first purchases, repeat orders, and skins per checkout. Compare campaign groups with a holdout to estimate incremental reach and sales. The effect of the small skin buff is still unmeasured. [Steamworks UTM Analytics](https://partner.steamgames.com/doc/marketing/utm_analytics)
