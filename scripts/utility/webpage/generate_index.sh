#!/bin/sh
# Regenerates public/index.html by listing every ticket folder under reports/
# Usage: sh scripts/generate_index.sh
set -e

REPORTS_SRC="reports"
PUBLIC_REPORTS="public/reports"
TEMPLATE="scripts/utility/webpage/index.template.html"
OUT="public/index.html"

mkdir -p "$PUBLIC_REPORTS"

# Bring the full tracked report history into this run's public/ output
if [ -d "$REPORTS_SRC" ]; then
  cp -r "$REPORTS_SRC"/. "$PUBLIC_REPORTS"/
fi

CARDS=""
if [ -d "$PUBLIC_REPORTS" ]; then
  for dir in $(ls -1t "$PUBLIC_REPORTS" 2>/dev/null); do
    if [ -f "$PUBLIC_REPORTS/$dir/index.html" ]; then
      CARDS="$CARDS
      <div class=\"report-card\" data-ticket=\"$dir\">
        <span class=\"ticket\">$dir</span>
        <div class=\"card-actions\">
          <a class=\"icon-btn\" href=\"reports/$dir/index.html\" title=\"View report\" aria-label=\"View report for $dir\">
            <svg viewBox=\"0 0 24 24\" fill=\"none\" stroke=\"currentColor\" stroke-width=\"2\" stroke-linecap=\"round\" stroke-linejoin=\"round\"><path d=\"M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z\"/><path d=\"M14 2v6h6\"/><line x1=\"8\" y1=\"13\" x2=\"16\" y2=\"13\"/><line x1=\"8\" y1=\"17\" x2=\"16\" y2=\"17\"/></svg>
          </a>
          <a class=\"icon-btn\" href=\"reports/$dir/log.html\" title=\"View logs\" aria-label=\"View logs for $dir\">
            <svg viewBox=\"0 0 24 24\" fill=\"none\" stroke=\"currentColor\" stroke-width=\"2\" stroke-linecap=\"round\" stroke-linejoin=\"round\"><polyline points=\"4 17 10 11 4 5\"/><line x1=\"12\" y1=\"19\" x2=\"20\" y2=\"19\"/></svg>
          </a>
        </div>
      </div>"
    fi
  done
fi

if [ -z "$CARDS" ]; then
  CARDS='      <div class="empty">No reports yet.</div>'
fi

# Iran Standard Time = UTC+3:30, Jalali calendar
TEHRAN_EPOCH=$(( $(date -u +%s) + 12600 ))
GY=$(date -u -d "@$TEHRAN_EPOCH" +%Y)
GM=$(date -u -d "@$TEHRAN_EPOCH" +%m)
GD=$(date -u -d "@$TEHRAN_EPOCH" +%d)
GH=$(date -u -d "@$TEHRAN_EPOCH" +%H)
GMIN=$(date -u -d "@$TEHRAN_EPOCH" +%M)

TIMESTAMP=$(awk -v gy="$GY" -v gm="$GM" -v gd="$GD" -v gh="$GH" -v gmin="$GMIN" '
BEGIN {
  split("31 28 31 30 31 30 31 31 30 31 30 31", g, " ")
  split("31 31 31 31 31 31 30 30 30 30 30 29", j, " ")
  gy2 = gy - 1600; gm2 = gm - 1; gd2 = gd - 1
  g_day_no = 365*gy2 + int((gy2+3)/4) - int((gy2+99)/100) + int((gy2+399)/400)
  for (i=1; i<=gm2; i++) g_day_no += g[i]
  leap = ((gy%4==0 && gy%100!=0) || gy%400==0)
  if (gm2 > 1 && leap) g_day_no += 1
  g_day_no += gd2
  j_day_no = g_day_no - 79
  j_np = int(j_day_no / 12053); j_day_no %= 12053
  jy = 979 + 33*j_np + 4*int(j_day_no/1461); j_day_no %= 1461
  if (j_day_no >= 366) { jy += int((j_day_no-1)/365); j_day_no = (j_day_no-1) % 365 }
  for (i=1; i<=11; i++) { if (j_day_no < j[i]) break; j_day_no -= j[i] }
  printf "%04d/%02d/%02d %s:%s", jy, i, j_day_no+1, gh, gmin
}')



awk -v cards="$CARDS" -v ts="$TIMESTAMP" '
  { gsub(/__CARDS__/, cards); gsub(/__TIMESTAMP__/, ts); print }
' "$TEMPLATE" > "$OUT"

echo "Wrote $OUT with $(echo "$CARDS" | grep -c report-card || true) report card(s)"
