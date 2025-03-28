import pandas as pd
import re
import requests
import streamlit as st
from bs4 import BeautifulSoup
from datetime import date, datetime
from typing import Dict
from typing import Optional
from typing import List


def fetch_html(url: str) -> Optional[BeautifulSoup]:
    """
    Fetch HTML content from a given URL

    Args:
        url (str): The URL to retrieve HTML from

    Returns:
        Optional[BeautifulSoup]: Parsed HTML content or None if an error occurs
    """
    try:
        # Send a GET request to the URL
        response = requests.get(url)

        # Raise an exception for bad status codes
        response.raise_for_status()

        # Parse the HTML content
        soup = BeautifulSoup(response.text, "html.parser")
        return soup

    except requests.RequestException as e:
        st.error(f"Error fetching URL: {e}")
        return None


def parse_pitcher_entry(entry: str) -> dict | None:
    """d
    Parse a pitcher entry string

    Args:
        entry (str): Raw pitcher entry string

    Returns:
        dict or None: Parsed information about the pitcher start
    """
    pattern = r"^(@)?\s*([A-Z]{3})\s*([A-Za-z\s]+)\s*\(([LR])\)$"
    match = re.match(pattern, entry)

    if match:
        return {
            "handedness": match.group(4),  # L or R
            "pitcher_name": match.group(3).strip(),  # Full pitcher name
            "formatted_opponent": f"{'@' if match.group(1) == '@' else 'v'} {match.group(2)}",
        }

    return None


def extract_dates_from_headers(soup: BeautifulSoup) -> Dict[int, str]:
    """
    Extract dates from table headers

    Args:
        soup (BeautifulSoup): Parsed HTML

    Returns:
        Dict[int, str]: Mapping of header index to date
    """
    # Find the first row of headers
    header_row = (
        soup.find("div", class_="table-scroll").find("table").find("tbody").find("tr")
    )

    # Extract dates from headers
    dates: Dict[int, str] = {}
    for idx, th in enumerate(header_row.find_all("th")[1:], start=1):
        # Look for date in the header text
        date_match = re.search(r"(\w{3})\s*(\d+/\d+)", th.get_text(strip=True))
        if date_match:
            # Construct a datetime object (using current year)
            day_name, month_day = date_match.groups()
            try:
                # Parse the month/day
                month, day = map(int, month_day.split("/"))

                # Determine the year based on month order
                current_year = datetime.now().year
                # If month is earlier than current month, assume next year
                # This handles the case of date ranges crossing year boundaries
                if month < datetime.now().month:
                    year = current_year + 1
                else:
                    year = current_year

                date_obj = datetime(year, month, day)
                dates[idx] = date_obj.strftime("%Y-%m-%d")
            except ValueError:
                # Skip if date parsing fails
                pass

    return dates


def extract_pitcher_starts(
    soup: BeautifulSoup, player_names: List[str]
) -> pd.DataFrame:
    """
    Extract pitcher starts from the HTML soup

    Args:
        soup (BeautifulSoup): Parsed HTML
        player_names (List[str]): List of player names to filter

    Returns:
        pd.DataFrame: DataFrame with pitcher starts
    """
    # Find the specific div with class "table-scroll"
    table_div = soup.find("div", class_="table-scroll")

    if not table_div:
        st.warning("Could not find table with class 'table-scroll'")
        return pd.DataFrame()

    # Find the table within the div
    table = table_div.find("table")

    if not table:
        st.warning("No table found within the 'table-scroll' div")
        return pd.DataFrame()

    # Extract dates from headers
    date_mapping: Dict[int, str] = extract_dates_from_headers(soup)

    # Extract table headers
    headers: List[str] = [th.get_text(strip=True) for th in table.find_all("th")]

    # Prepare to store parsed data
    parsed_rows: List[Dict[str, str]] = []

    # Extract table rows
    for tr in table.find_all("tr")[1:]:  # Skip header row
        row_data: List[str] = [td.get_text(strip=True) for td in tr.find_all("td")]

        # Process every item in the row
        row_entries: List[Dict[str, str]] = []
        for col_idx, item in enumerate(row_data, start=1):
            parsed_entry: Optional[Dict[str, str]] = parse_pitcher_entry(item)

            if parsed_entry:
                # Check if pitcher should be included (if player names provided)
                if (
                    not player_names
                    or parsed_entry["pitcher_name"].lower() in player_names
                ):
                    # Combine parsed entry with rest of row data
                    full_row: Dict[str, str] = {
                        "Date": date_mapping.get(col_idx - 1, "Unknown"),
                        "Handedness": parsed_entry["handedness"],
                        "Pitcher": parsed_entry["pitcher_name"],
                        "Opponent": parsed_entry["formatted_opponent"],
                    }
                    row_entries.append(full_row)

        # Add all found entries for this row
        parsed_rows.extend(row_entries)

    # Sort parsed_rows by date
    parsed_rows.sort(key=lambda x: x["Date"])

    # Create DataFrame
    return pd.DataFrame(parsed_rows)


def main():
    st.set_page_config(page_title="SP Probables Tracker")
    st.title("Fantasy SP Probables Tracker")

    # URL input for HTML source
    url = "https://www.fangraphs.com/roster-resource/probables-grid"

    # Date input section
    col1, col2 = st.columns(2)
    with col1:
        start_date = st.date_input("Start Date", value=date.today())
    with col2:
        max_date = date.today() + pd.Timedelta(days=10)
        end_date = st.date_input(
            "End Date (max 10 days from today)", value=date.today(), max_value=max_date
        )

    # Player name input
    player_names = st.text_area(
        "Enter Player Names:",
        placeholder="Enter each player name on a new line",
        help="List the pitcher names you want to track, one per line",
    )

    # Process button
    if st.button("Find Pitcher Starts"):
        # Validate inputs
        if not url:
            st.warning("Please enter a URL")
            return

        # Convert player names to a list
        players = [
            name.strip().lower() for name in player_names.split("\n") if name.strip()
        ]

        # Fetch and process HTML
        html_soup = fetch_html(url)

        if html_soup:
            # Extract pitcher starts
            pitcher_starts = extract_pitcher_starts(html_soup, players)

            # Display results
            if not pitcher_starts.empty:
                st.subheader("Pitcher Starts")
                st.dataframe(pitcher_starts)
            else:
                st.warning("No pitcher starts found")


if __name__ == "__main__":
    main()
