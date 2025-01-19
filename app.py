from flask import Flask, render_template, request
from datetime import date, timedelta

app = Flask(__name__)


# ----------------------------------------------------------------
# 1) Determine if a (Gregorian) year is leap
# ----------------------------------------------------------------
def is_leap_year(year):
    """Standard Gregorian leap-year rules."""
    if year % 400 == 0:
        return True
    if year % 100 == 0:
        return False
    if year % 4 == 0:
        return True
    return False


# ----------------------------------------------------------------
# 2) Convert a single Gregorian date -> IFC date string
#    e.g. "January 1", "Leap Day", "Year Day", etc.
# ----------------------------------------------------------------
def greg_to_ifc_string(year, month, day):
    """
    Returns a string describing the IFC date for the given Gregorian Y/M/D.
    Possibilities:
      - "January 1" .. "Sol 28"
      - "Leap Day"
      - "Year Day"
    Returns None if the Gregorian date is invalid or out of range.
    """

    # Validate the Gregorian date
    try:
        g_date = date(year, month, day)
    except ValueError:
        return None  # invalid (e.g., April 31)

    day_of_year = (g_date - date(year, 1, 1)).days + 1
    leap = is_leap_year(year)
    days_in_year = 366 if leap else 365
    if day_of_year < 1 or day_of_year > days_in_year:
        return None

    # IFC logic:
    #  - First 6 months of 28 days => 168
    #  - If leap => day 169 = Leap Day
    #  - Next 7 months of 28 => total 364
    #  - Final day = Year Day (day 365)
    #  - In a leap year, day 366 is also effectively Year Day offset logic

    # We'll do an arithmetic approach:
    if day_of_year <= 168:
        # It's in months 0..5 (Jan..June)
        m_idx = (day_of_year - 1) // 28
        d_in_month = ((day_of_year - 1) % 28) + 1
        return f"{ifc_month_name(m_idx)} {d_in_month}"

    # Else we've passed the first 168 days
    current_day = 169

    if leap:
        # If day_of_year == 169 => Leap Day
        if day_of_year == 169:
            return "Leap Day"
        # If day_of_year > 169 => shift by 1
        if day_of_year > 169:
            day_of_year -= 1
        current_day = 170

    # Now we have months 6..12 => 7 * 28 = 196 days
    # day_of_year vs current_day
    if day_of_year < current_day + 28 * 7:
        # It's within these 7 months
        offset = day_of_year - current_day
        m_idx = (offset // 28) + 6
        d_in_month = (offset % 28) + 1
        return f"{ifc_month_name(m_idx)} {d_in_month}"

    # Otherwise => Year Day
    return "Year Day"


def ifc_month_name(index_0_based):
    """Return the IFC month name for index 0..12 => Jan..Sol."""
    month_names = [
        "Jan", "Feb", "Mar", "Apr", "May", "Jun",
        "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
        "Sol"
    ]
    return month_names[index_0_based]


# ----------------------------------------------------------------
# 3) Superimpose a single Gregorian month
#    Return a structure for templating: 
#    { "year": gy, "month": gm, "month_name": e.g. "March",
#      "weeks": [
#         [ { "greg_day": 1, "ifc_str": "January 28" }, ..., up to 7 ],
#         [ ... up to 6 rows potentially ],
#      ]
#    }
# ----------------------------------------------------------------
def superimpose_single_month(gy, gm):
    """
    Build a calendar-like data structure for the given Gregorian month (gy/gm).
    Each "week" is a list of up to 7 dictionaries.
      { "greg_day": day_of_month, "ifc_str": "January 1" or "Leap Day"/"Year Day"/None }
    If a cell is outside the valid day range, we can omit it or mark it as None.
    """
    # 1) Figure out how many days in this month
    #    A simple approach: increment from day=1 until error
    #    or use calendar.monthrange in Python, but let's keep it minimal.
    try:
        first_day = date(gy, gm, 1)
    except ValueError:
        return None  # invalid e.g. month=13

    # Count days in this month
    days_in_month = 0
    while True:
        try:
            test_date = date(gy, gm, days_in_month + 1)
            days_in_month += 1
        except ValueError:
            break

    # 2) Build the "weeks" array. We'll do a simple approach:
    #    We need to figure out the weekday of the 1st day to place it properly if we want
    #    a typical "calendar" layout. But the user didn't specify that we must align weekdays.
    #    So we can just chunk days into rows of 7. 
    #    If you want real weekday alignment, you'd do test_date.weekday() etc.
    #    We'll keep it simpler: row 1 => days 1..7, row 2 => days 8..14, etc.

    # For each day, compute IFC string
    def day_ifc_str(d):
        return greg_to_ifc_string(gy, gm, d) or "--"

    weeks = []
    day_counter = 1
    while day_counter <= days_in_month:
        row = []
        for _ in range(7):
            if day_counter <= days_in_month:
                row.append({
                    "greg_day": day_counter,
                    "ifc_str": day_ifc_str(day_counter)
                })
                day_counter += 1
            else:
                break  # no more days
        weeks.append(row)

    return {
        "year": gy,
        "month": gm,
        "month_name": date(gy, gm, 1).strftime("%B"),  # e.g. "March"
        "weeks": weeks
    }


# ----------------------------------------------------------------
# 4) Superimpose an entire Gregorian year (12 months)
# ----------------------------------------------------------------
def superimpose_entire_year(gy):
    """
    Return a list of 12 "month data" dicts, each in the same format
    as superimpose_single_month(gy, gm).
    """
    months_data = []
    for m in range(1, 13):
        md = superimpose_single_month(gy, m)
        if md:  # should always be valid for 1..12
            months_data.append(md)
    return months_data


# ----------------------------------------------------------------
# 5) Flask Routes
# ----------------------------------------------------------------
@app.route('/', methods=['GET'])
def index():
    """Single form with 3 fields: year (required), month (optional), day (optional)."""
    return render_template('index.html')


@app.route('/show', methods=['POST'])
def show():
    """
    Interprets the 3 fields:
      - if only 'year' => superimpose the entire year
      - if 'year' and 'month' => superimpose that month
      - if 'year', 'month', and 'day' => single day => result.html
    """
    year_str = request.form.get('year', '').strip()
    month_str = request.form.get('month', '').strip()
    day_str = request.form.get('day', '').strip()

    if not year_str:
        return "Year is required."

    # Convert year
    try:
        gy = int(year_str)
    except ValueError:
        return "Invalid year."

    if not month_str:
        # (A) year only => entire year
        data = superimpose_entire_year(gy)
        return render_template('superimposed_year.html', year=gy, months_data=data)

    # otherwise, we have a month
    try:
        gm = int(month_str)
    except ValueError:
        return "Invalid month."
    if gm < 1 or gm > 12:
        return "Month must be in 1..12"

    if not day_str:
        # (B) year + month => single month
        data = superimpose_single_month(gy, gm)
        if not data:
            return f"Invalid year/month combination: {gy}-{gm}"
        return render_template('superimposed_month.html', data=data)
    else:
        # (C) year + month + day => single day => result.html
        try:
            gd = int(day_str)
        except ValueError:
            return "Invalid day."

        # Quick check if the Gregorian date is valid
        try:
            test_date = date(gy, gm, gd)
        except ValueError:
            return f"Invalid date: {gy}-{gm}-{gd}."

        ifc_str = greg_to_ifc_string(gy, gm, gd)
        if not ifc_str:
            return f"Date is out of range: {gy}-{gm}-{gd}."

        return render_template(
            'result.html',
            greg_year=gy,
            greg_month=gm,
            greg_day=gd,
            ifc_str=ifc_str
        )


if __name__ == '__main__':
    app.run(debug=True)
