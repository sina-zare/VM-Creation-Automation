#!/bin/sh

# Renders reports/<TICKET>/log.html from automation.log.
# Each JSON log line is pretty-printed with jq and HTML-escaped.
# Invalid JSON lines are preserved as raw HTML-escaped text.
#
# Usage:
#   sh scripts/generate_log.sh <TICKET_KEY>

set -eu

TICKET="${1:-}"

if [ -z "$TICKET" ]; then
    echo "Usage: $0 <TICKET_KEY>" >&2
    exit 1
fi

LOG_FILE="automation.log"
TEMPLATE="scripts/utility/webpage/log.template.html"

OUT_DIR="reports/$TICKET"
FORMATTED="$OUT_DIR/.log_formatted.html"

mkdir -p "$OUT_DIR"

# Start with an empty formatted log.
: > "$FORMATTED"


###############################################################################
# HTML escape
###############################################################################

html_escape() {
    sed \
        -e 's/&/\&amp;/g' \
        -e 's/</\&lt;/g' \
        -e 's/>/\&gt;/g'
}


###############################################################################
# Process automation.log
###############################################################################

if [ -f "$LOG_FILE" ]; then

    while IFS= read -r line || [ -n "$line" ]; do

        # Skip empty lines.
        [ -z "$line" ] && continue

        # Try to parse and pretty-print the JSON.
        #
        # jq automatically produces:
        #
        # {
        #   "asctime": "...",
        #   "levelname": "INFO",
        #   ...
        # }
        #
        if PRETTY=$(printf '%s\n' "$line" | jq '.' 2>/dev/null); then

            # HTML-escape the pretty JSON.
            #
            # IMPORTANT:
            # Do NOT use:
            #     | html_escape
            #
            # directly here. We explicitly invoke the shell function.
            printf '%s\n' "$PRETTY" | html_escape >> "$FORMATTED"

        else

            # Invalid JSON:
            # preserve the original line, but HTML-escape it.
            printf '%s\n' "$line" | html_escape >> "$FORMATTED"

        fi

        # Blank line between log entries.
        printf '\n' >> "$FORMATTED"

    done < "$LOG_FILE"

else

    printf '%s\n' \
        "(no automation.log produced for this run)" \
        >> "$FORMATTED"

fi


###############################################################################
# Tehran timestamp
###############################################################################

# Iran Standard Time = UTC+3:30
TEHRAN_EPOCH=$(( $(date -u +%s) + 12600 ))

GY=$(date -u -d "@$TEHRAN_EPOCH" +%Y)
GM=$(date -u -d "@$TEHRAN_EPOCH" +%m)
GD=$(date -u -d "@$TEHRAN_EPOCH" +%d)
GH=$(date -u -d "@$TEHRAN_EPOCH" +%H)
GMIN=$(date -u -d "@$TEHRAN_EPOCH" +%M)

TIMESTAMP=$(awk \
    -v gy="$GY" \
    -v gm="$GM" \
    -v gd="$GD" \
    -v gh="$GH" \
    -v gmin="$GMIN" '
BEGIN {

    split("31 28 31 30 31 30 31 31 30 31 30 31", g, " ")
    split("31 31 31 31 31 31 30 30 30 30 30 29", j, " ")

    gy2 = gy - 1600
    gm2 = gm - 1
    gd2 = gd - 1

    g_day_no = 365 * gy2 \
             + int((gy2 + 3) / 4) \
             - int((gy2 + 99) / 100) \
             + int((gy2 + 399) / 400)

    for (i = 1; i <= gm2; i++)
        g_day_no += g[i]

    leap = ((gy % 4 == 0 && gy % 100 != 0) || gy % 400 == 0)

    if (gm2 > 1 && leap)
        g_day_no += 1

    g_day_no += gd2

    j_day_no = g_day_no - 79

    j_np = int(j_day_no / 12053)
    j_day_no %= 12053

    jy = 979 \
       + 33 * j_np \
       + 4 * int(j_day_no / 1461)

    j_day_no %= 1461

    if (j_day_no >= 366) {
        jy += int((j_day_no - 1) / 365)
        j_day_no = (j_day_no - 1) % 365
    }

    for (i = 1; i <= 11; i++) {
        if (j_day_no < j[i])
            break

        j_day_no -= j[i]
    }

    printf "%04d/%02d/%02d %s:%s",
        jy,
        i,
        j_day_no + 1,
        gh,
        gmin
}')


###############################################################################
# Generate final HTML
###############################################################################

awk \
    -v ticket="$TICKET" \
    -v ts="$TIMESTAMP" \
    -v logfile="$FORMATTED" '
    /__LOG_CONTENT__/ {
        while ((getline line < logfile) > 0)
            print line

        close(logfile)
        next
    }

    {
        gsub(/__TICKET_KEY__/, ticket)
        gsub(/__TIMESTAMP__/, ts)
        print
    }
' "$TEMPLATE" > "$OUT_DIR/log.html"


###############################################################################
# Cleanup
###############################################################################

rm -f "$FORMATTED"

echo "Wrote $OUT_DIR/log.html"
