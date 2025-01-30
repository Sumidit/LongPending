import streamlit as st
import pandas as pd
import re
import time
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager

# URLs and login credentials
LOGIN_URL = "http://172.20.17.50/phoenix/public/"
DASHBOARD_URL = {
    "For Info Site": "http://172.20.17.50/phoenix/public/dashboard_fault_view?dashboard_value=info_banbeis#site_fault_list_table",
    "For Info Link": "http://172.20.17.50/phoenix/public/dashboard_fault_view?dashboard_value=info_banbeis#link_fault_list_table",
    "For SComm site": "http://172.20.17.50/phoenix/public/dashboard_fault_view?dashboard_value=long_pending",  # New URL for SComm site
    "For SComm Link": "http://172.20.17.50/phoenix/public/dashboard_fault_view?dashboard_value=long_pending"  # New URL for SComm Link
}
USERNAME = "s.paul@summit-towers.net"
PASSWORD = "M@rvel4408"

# Function to fetch data from the site based on the selected dashboard URL
def fetch_data(dashboard_key):
    try:
        # Setup Selenium WebDriver
        options = webdriver.ChromeOptions()
        options.add_argument("--headless")
        driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)

        # Step 1: Login to the portal
        driver.get(LOGIN_URL)
        time.sleep(3)

        driver.find_element(By.NAME, "username").send_keys(USERNAME)
        driver.find_element(By.NAME, "password").send_keys(PASSWORD)
        driver.find_element(By.NAME, "password").send_keys(Keys.RETURN)
        time.sleep(5)

        # Step 2: Navigate to the selected dashboard URL
        driver.get(DASHBOARD_URL[dashboard_key])
        time.sleep(5)

        # Step 3: Extract the table data (first or second table depending on the page)
        tables = driver.find_elements(By.TAG_NAME, "table")  # Find all tables on the page

        if dashboard_key == "For SComm site" or dashboard_key == "For Info Site":
            table = tables[0]  # For the first table (SComm site or Info Site)
        elif dashboard_key == "For SComm Link" or dashboard_key == "For Info Link":
            if len(tables) > 1:
                table = tables[1]  # For the second table (SComm Link or Info Link)
            else:
                st.error("Second table not found on the page.")
                driver.quit()
                return

        rows = table.find_elements(By.TAG_NAME, "tr")

        data = []
        for row in rows:
            cols = row.find_elements(By.TAG_NAME, "td")
            if cols:
                data.append([col.text for col in cols])

        driver.quit()

        # Convert data to DataFrame
        df = pd.DataFrame(data, columns=[  # Same column structure for both site and link tables
            "Fault ID", "Problem Category", "Element Name", "Client", "Region",
            "Sub Center", "Impact", "Event Time", "Duration", "Responsible Concern",
            "Ticket Comments", "Task Comments", "Dept Working on this TT", "View / Edit"
        ])

        # Save data to session state
        st.session_state["df"] = df

        st.success(f"Dashboard data extracted successfully for '{dashboard_key}'!")
        st.dataframe(df)  # Display the dataframe in Streamlit

    except Exception as e:
        st.error(f"Failed to fetch data: {e}")

# Function to generate notifications
def generate_notification(df, selected_dept, selected_client, selected_problem):
    try:
        # Apply filter based on selected Dept Working on this TT
        if selected_dept != "All":
            filtered_df = df[df["Dept Working on this TT"] == selected_dept]
        else:
            filtered_df = df.copy()

        # Apply filter based on selected Client
        if selected_client != "All":
            filtered_df = filtered_df[filtered_df["Client"] == selected_client]

        # Apply filter based on selected Problem Category
        if selected_problem != "All":
            filtered_df = filtered_df[filtered_df["Problem Category"] == selected_problem]

        notifications = []

        # Iterate over each unique Subcenter to create notifications
        for subcenter in filtered_df["Sub Center"].unique():
            sub_df = filtered_df[filtered_df["Sub Center"] == subcenter]

            # Get the Dept (Dept Working on this TT) and Client Name(s) associated with this Subcenter
            dept = sub_df["Dept Working on this TT"].unique().tolist()
            clients = sub_df["Client"].unique().tolist()

            client_notifications = []
            for client in clients:
                client_data = sub_df[sub_df["Client"] == client]
                
                # Extract TT IDs inside parentheses from the Fault ID column for the specific client
                tt_ids = client_data["Fault ID"].apply(lambda x: re.findall(r"\(.*?\)", x)).explode().dropna().unique().tolist()
                tt_ids = [id.strip("()") for id in tt_ids]  # Remove brackets

                # Extract Durations for each TT ID
                durations = {}
                for tt_id in tt_ids:
                    # Find the row corresponding to this TT ID and extract its duration
                    tt_row = client_data[client_data["Fault ID"].str.contains(tt_id)]
                    if not tt_row.empty:
                        duration = tt_row["Duration"].values[0]  # Get the duration of this TT ID
                        durations[tt_id] = duration
                
                # Add Client Name and TT IDs with Duration to the notification
                client_notifications.append(f"{client} TT IDs: " + ", ".join([f"{tt_id} ({durations[tt_id]})" for tt_id in tt_ids]))

            # Format the notification message
            message = (
                f"**Dept Working on this TT:** {', '.join(dept)}\n"
                f"**Client Name(s):** {', '.join(client_notifications)}\n"
                f"**Subcenter:** {subcenter}"
            )
            notifications.append(message)

        return notifications
    except Exception as e:
        return [f"Error processing data: {e}"]

# Streamlit UI
st.title("LongPending TT Finder ⏳")

# Dropdown for selecting data collection site (removed "Other Site")
selected_site = st.selectbox("Data Collection", ["For Info Site", "For Info Link", "For SComm site", "For SComm Link"])

# Button to fetch and process data based on selection
if selected_site in DASHBOARD_URL:
    if st.button(f"Start and Process Data ({selected_site})"):
        fetch_data(selected_site)

# UI for filtering and notifications
if "df" in st.session_state:
    df = st.session_state["df"]

    client_names = df["Client"].dropna().unique().tolist()
    problem_categories = df["Problem Category"].dropna().unique().tolist()
    dept_working_list = df["Dept Working on this TT"].dropna().unique().tolist()  # Fetch data from the "Dept Working on this TT" column

    # Add "All" option to the Dept Working on this TT selection dropdown
    selected_client = st.selectbox("Select Client Name", ["All"] + client_names)
    selected_problem = st.selectbox("Select Problem Category", ["All"] + problem_categories)
    selected_dept = st.selectbox("Select Dept Working on this TT", ["All"] + dept_working_list)  # Renamed to "Dept Working on this TT"

    # Apply filtering based on selections
    filtered_df = df.copy()
    if selected_client != "All":
        filtered_df = filtered_df[filtered_df["Client"] == selected_client]
    if selected_problem != "All":
        filtered_df = filtered_df[filtered_df["Problem Category"] == selected_problem]

    # If "All" Dept Working on this TT is selected, don't apply any filter
    if selected_dept != "All":
        filtered_df = filtered_df[filtered_df["Dept Working on this TT"] == selected_dept]  # Filter based on the new column

    st.dataframe(filtered_df)

    # Show Dept-wise Count for Fault ID (Now based on Dept Working on this TT)
    dept_count_df = filtered_df.groupby("Dept Working on this TT")["Fault ID"].count().reset_index()
    dept_count_df.rename(columns={"Fault ID": "Dept-wise Count"}, inplace=True)

    st.subheader("Dept-wise Count")
    st.dataframe(dept_count_df)

    # Show Subcenter-wise Count for Fault ID
    subcenter_count_df = filtered_df.groupby("Sub Center")["Fault ID"].count().reset_index()
    subcenter_count_df.rename(columns={"Fault ID": "Subcenter-wise Count"}, inplace=True)

    st.subheader("Subcenter-wise Count")
    st.dataframe(subcenter_count_df)

    # Button to generate notification
    if st.button("Generate"):
        notification_messages = generate_notification(df, selected_dept, selected_client, selected_problem)  # Use selected_dept for notification generation

        for msg in notification_messages:
            st.info(msg)
