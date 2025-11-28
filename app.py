import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime, timedelta
import os
import pdfkit

pdf_config = pdfkit.configuration(
    wkhtmltopdf=r"C:\Program Files\wkhtmltopdf\bin\wkhtmltopdf.exe"
)

# -------------------- CONFIG --------------------
DB_PATH = "billboards.db"
DEFAULT_COLS = [
    'Billboard Number', 'Billboard ID', 'Location', 'Billboard Size',
    'Client Name', 'Company Name', 'Contact Number', 'Email',
    'Contract Start Date', 'Contract End Date', 'Rental Duration',
    'Rent Amount (PKR)', 'Advance Received (PKR)', 'Balance / Credit (PKR)',
    'Payment Status', 'Contract Status', 'Days Remaining',
    'Remarks / Notes', 'Image / Link', 'Partner’s share'
]
MAX_BOARDS = 50

st.set_page_config(page_title="Billboard Manager — Pro", layout="wide")
st.title("📊 Billboard Rental Manager — Pro")

# -------------------- SIDEBAR SETTINGS --------------------
st.sidebar.header("Settings")
use_sql = st.sidebar.checkbox("Use SQLite persistence", value=True)
auto_save = st.sidebar.checkbox("Auto-save after actions", value=True)
alert_days = st.sidebar.number_input("Alert before expiry (days)", min_value=0, max_value=365, value=7)

# -------------------- HELPERS --------------------
def fmt_money(val):
    try:
        if val is None or (isinstance(val, float) and pd.isna(val)) or str(val).strip() == "":
            return ""
        return f"{float(val):,.0f}"
    except:
        return str(val)

def init_db_if_missing(conn):
    cur = conn.cursor()
    cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = {r[0] for r in cur.fetchall()}
    if 'dashboard' not in tables or 'saveddata' not in tables or 'summary' not in tables:
        df = pd.DataFrame(columns=DEFAULT_COLS)
        df.to_sql('dashboard', conn, index=False, if_exists='replace')
        df.to_sql('saveddata', conn, index=False, if_exists='replace')
        pd.DataFrame({'Total Boards':[MAX_BOARDS]}).to_sql('summary', conn, index=False, if_exists='replace')

def read_sheets_sqlite():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    try:
        init_db_if_missing(conn)
        dashboard = pd.read_sql_query('SELECT * FROM dashboard', conn)
        saved = pd.read_sql_query('SELECT * FROM saveddata', conn)
        summary = pd.read_sql_query('SELECT * FROM summary', conn)

        for df in (dashboard, saved):
            for c in df.columns:
                if any(k in c.lower() for k in ['date','start','end','from','to']):
                    df[c] = pd.to_datetime(df[c], errors='coerce')

        return dashboard, summary, saved
    finally:
        conn.close()

def save_to_db(dashboard_df, summary_df, saved_df):
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    dashboard_df.to_sql('dashboard', conn, index=False, if_exists='replace')
    saved_df.to_sql('saveddata', conn, index=False, if_exists='replace')
    summary_df.to_sql('summary', conn, index=False, if_exists='replace')
    conn.close()

def compute_status(end_val, alert_days_local):
    try:
        if pd.isna(end_val) or str(end_val).strip() == "":
            return 'Available'
        end_dt = pd.to_datetime(end_val)
    except:
        return 'Unknown'

    today = pd.Timestamp(datetime.today().date())
    if end_dt < today:
        return 'Expired'
    if end_dt <= today + pd.Timedelta(days=alert_days_local):
        return 'Expiring Soon'
    return 'Booked'


# -------------------- LOAD / INIT --------------------
if 'initialized' not in st.session_state:
    st.session_state.initialized = True

    if use_sql and os.path.exists(DB_PATH):
        try:
            dash, summ, saved = read_sheets_sqlite()
        except:
            dash = pd.DataFrame(columns=DEFAULT_COLS)
            saved = pd.DataFrame(columns=DEFAULT_COLS)
            summ = pd.DataFrame({'Total Boards':[MAX_BOARDS]})
    elif use_sql:
        conn = sqlite3.connect(DB_PATH)
        init_db_if_missing(conn)
        conn.close()
        dash, summ, saved = read_sheets_sqlite()
    else:
        dash = pd.DataFrame(columns=DEFAULT_COLS)
        saved = pd.DataFrame(columns=DEFAULT_COLS)
        summ = pd.DataFrame({'Total Boards':[MAX_BOARDS]})

    if 'Billboard Number' not in dash.columns:
        dash = dash.reindex(columns=["Billboard Number"] + [c for c in DEFAULT_COLS if c != 'Billboard Number'])

    if len(dash) < MAX_BOARDS:
        n_add = MAX_BOARDS - len(dash)
        add_df = pd.DataFrame([[""]*len(dash.columns)] * n_add, columns=dash.columns)
        dash = pd.concat([dash, add_df], ignore_index=True)

    dash['Billboard Number'] = list(range(1, MAX_BOARDS+1))

    st.session_state.dashboard_df = dash.reset_index(drop=True)
    st.session_state.saved_df = saved.reset_index(drop=True)
    st.session_state.summary_df = summ

dashboard_df = st.session_state.dashboard_df
saved_df = st.session_state.saved_df
summary_df = st.session_state.summary_df

# -------------------- MAIN MENU --------------------
menu = st.sidebar.radio('View', ['Dashboard', 'Summary', 'Saved Data', 'Admin', 'Print'])
# -------------------- DASHBOARD --------------------
if menu == 'Dashboard':

    st.header("📋 Dashboard — Select / Edit / Quick Add")

    # STATUS UPDATE
    end_col = "Contract End Date"
    dashboard_df["Status"] = [
        compute_status(dashboard_df.at[i, end_col], alert_days)
        for i in range(len(dashboard_df))
    ]

    # SELECT COLUMN
    if "Select" not in dashboard_df.columns:
        dashboard_df.insert(0, "Select", False)
    dashboard_df["Select"] = dashboard_df["Select"].astype(bool)

    edited = st.data_editor(
        dashboard_df,
        use_container_width=True,
        num_rows="dynamic",
        column_config={
            "Select": st.column_config.CheckboxColumn(required=False),
            "Billboard Number": st.column_config.NumberColumn(disabled=True),
        },
        key="dashboard_editor"
    )

    # SELECTED ROWS
    selected_rows = edited.index[edited["Select"] == True].tolist() if "Select" in edited.columns else []

    col_apply, col_archive, col_delete = st.columns(3)

    # APPLY EDITS
    with col_apply:
        if st.button("Apply Edits"):
            st.session_state.dashboard_df = edited.copy()
            if auto_save and use_sql:
                save_to_db(edited, summary_df, saved_df)
            st.success("✔ Changes Saved")
            st.rerun()

    # ARCHIVE SELECTED
    with col_archive:
        if st.button("Archive Selected → Saved"):
            if not selected_rows:
                st.warning("⚠ کوئی row منتخب نہیں کی گئی۔")
            else:
                dash_copy = edited.copy()
                archive_block = []
                for idx in selected_rows:
                    r = dash_copy.iloc[idx].copy()
                    r["Archived At"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    archive_block.append(r)
                    for col in dash_copy.columns:
                        if col not in ["Billboard Number", "Select"]:
                            dash_copy.at[idx, col] = ""
                st.session_state.saved_df = pd.concat([saved_df, pd.DataFrame(archive_block)], ignore_index=True)
                st.session_state.dashboard_df = dash_copy

                if auto_save and use_sql:
                    save_to_db(dash_copy, summary_df, st.session_state.saved_df)

                st.success("✔ Rows Archived")
                st.rerun()

    # DELETE SELECTED
    with col_delete:
        if st.button("🗑️ Delete Selected"):
            if not selected_rows:
                st.warning("⚠ کوئی row منتخب نہیں کی گئی۔")
            else:
                dash_copy = edited.copy()
                for idx in selected_rows:
                    for col in dash_copy.columns:
                        if col not in ["Billboard Number", "Select"]:
                            dash_copy.at[idx, col] = ""
                st.session_state.dashboard_df = dash_copy

                if auto_save and use_sql:
                    save_to_db(dash_copy, summary_df, saved_df)

                st.success("✔ Rows Cleared")
                st.rerun()


    # -------------------- QUICK ADD PANEL --------------------
    st.markdown("---")
    st.subheader("➕ Quick Add / Auto-Fill")

    # Slot selection
    col_slot1, col_slot2 = st.columns([2, 1])
    with col_slot1:
        choices = ["🪧 Auto (First Empty Slot)"] + [
            f"Billboard {i}" for i in range(1, MAX_BOARDS + 1)
        ]
        choice = st.selectbox("🎯 Target Slot:", choices)
    with col_slot2:
        overwrite = st.checkbox("🔄 Overwrite Existing", value=False)

    chosen_idx = None
    if choice != "🪧 Auto (First Empty Slot)":
        chosen = int(choice.split()[-1])
        idx_list = dashboard_df.index[dashboard_df["Billboard Number"] == chosen].tolist()
        if idx_list:
            chosen_idx = idx_list[0]

    st.write("### 📝 Fill Details")

    with st.form("quick_add_form", clear_on_submit=False):
        col1, col2, col3 = st.columns(3)

        with col1:
            bb_id = st.text_input("Billboard ID")
            location = st.text_input("Location / Address")
            size = st.text_input("Billboard Size (e.g. 20x10 ft)")
            client = st.text_input("Client Name")
            company = st.text_input("Company Name")

        with col2:
            contact = st.text_input("Contact Number")
            email = st.text_input("Client Email")
            start_date = st.date_input("Start Date", datetime.today())
            end_date = st.date_input("End Date", datetime.today() + timedelta(days=30))
            duration = st.text_input("Contract Duration (e.g. 1 Month)")

        with col3:
            col_rent, col_adv, col_bal = st.columns(3)

            with col_rent:
                rent = st.number_input("Rent (PKR)", min_value=0.0, step=1000.0)
            with col_adv:
                adv = st.number_input("Advance (PKR)", min_value=0.0, step=1000.0)

            balance = rent - adv

            with col_bal:
                st.markdown("**Balance (PKR)**")
                st.info(f"{balance:,.2f}")

            pay_status = st.selectbox("Payment Status", ["Pending", "Paid", "Partial", "Overdue"])
            contract_status = st.selectbox("Contract Status", ["Active", "Completed", "Cancelled"])

        st.write("### 🧾 Extra Info")
        remarks = st.text_area("Remarks / Notes")
        colx1, colx2 = st.columns(2)
        with colx1:
            img_link = st.text_input("📷 Image Link / URL")
        with colx2:
            partner_share = st.text_input("💼 Partner’s Share (if any)")

        submitted = st.form_submit_button("✅ Add Billboard Entry")

    if submitted:
        target = None

        # Auto slot detection
        if choice == "🪧 Auto (First Empty Slot)":
            for i in range(len(dashboard_df)):
                row = dashboard_df.iloc[i]
                if all(str(row[c]).strip() == "" for c in dashboard_df.columns if c not in ["Billboard Number", "Select", "Status"]):
                    target = i
                    break
        else:
            target = chosen_idx
            if target is not None and not overwrite:
                row = dashboard_df.iloc[target]
                if any(str(row[c]).strip() != "" for c in dashboard_df.columns if c not in ["Billboard Number", "Select", "Status"]):

                    st.error("❌ Slot already occupied! Enable Overwrite option.")
                    target = None

        if target is None:
            st.error("⚠ Empty slot not found.")
        else:
            dashboard_df.at[target, "Billboard ID"] = bb_id
            dashboard_df.at[target, "Location"] = location
            dashboard_df.at[target, "Billboard Size"] = size
            dashboard_df.at[target, "Client Name"] = client
            dashboard_df.at[target, "Company Name"] = company
            dashboard_df.at[target, "Contact Number"] = contact
            dashboard_df.at[target, "Email"] = email
            dashboard_df.at[target, "Contract Start Date"] = start_date
            dashboard_df.at[target, "Contract End Date"] = end_date
            dashboard_df.at[target, "Rental Duration"] = duration
            dashboard_df.at[target, "Rent Amount (PKR)"] = rent
            dashboard_df.at[target, "Advance Received (PKR)"] = adv
            dashboard_df.at[target, "Balance / Credit (PKR)"] = balance
            dashboard_df.at[target, "Payment Status"] = pay_status
            dashboard_df.at[target, "Contract Status"] = contract_status
            dashboard_df.at[target, "Remarks / Notes"] = remarks
            dashboard_df.at[target, "Image / Link"] = img_link
            dashboard_df.at[target, "Partner’s share"] = partner_share
            dashboard_df.at[target, "Days Remaining"] = (
                pd.Timestamp(end_date) - pd.Timestamp(datetime.today().date())
            ).days

        if target is None:
            st.error("⚠ Empty slot not found.")
        else:
            dashboard_df.at[target, "Billboard ID"] = bb_id
            dashboard_df.at[target, "Location"] = location
            dashboard_df.at[target, "Billboard Size"] = size
            dashboard_df.at[target, "Client Name"] = client
            dashboard_df.at[target, "Company Name"] = company
            dashboard_df.at[target, "Contact Number"] = contact
            dashboard_df.at[target, "Email"] = email
            dashboard_df.at[target, "Contract Start Date"] = start_date
            dashboard_df.at[target, "Contract End Date"] = end_date
            dashboard_df.at[target, "Rental Duration"] = duration
            dashboard_df.at[target, "Rent Amount (PKR)"] = rent
            dashboard_df.at[target, "Advance Received (PKR)"] = adv
            dashboard_df.at[target, "Balance / Credit (PKR)"] = balance
            dashboard_df.at[target, "Payment Status"] = pay_status
            dashboard_df.at[target, "Contract Status"] = contract_status
            dashboard_df.at[target, "Remarks / Notes"] = remarks
            dashboard_df.at[target, "Image / Link"] = img_link
            dashboard_df.at[target, "Partner’s share"] = partner_share
            dashboard_df.at[target, "Days Remaining"] = (
                pd.Timestamp(end_date) - pd.Timestamp(datetime.today().date())
            ).days

            st.session_state.dashboard_df = dashboard_df.copy()

            if auto_save and use_sql:
                save_to_db(dashboard_df, summary_df, saved_df)

            st.success("✅ Billboard entry added successfully!")
            st.rerun()
# -------------------- SUMMARY --------------------
elif menu == 'Summary':

    st.header("📈 Summary — Stats & Filters")

    # Merge dashboard + saved for reporting only
    full = pd.concat(
        [st.session_state.dashboard_df, st.session_state.saved_df],
        ignore_index=True,
        sort=False
    )

    # Stats
    total_boards = MAX_BOARDS
    occupied = full[full['Client Name'].astype(str).str.strip() != '']
    num_booked = occupied.shape[0]
    num_available = total_boards - num_booked

    c1, c2, c3 = st.columns(3)
    c1.metric('Total Boards', total_boards)
    c2.metric('Booked / Occupied', int(num_booked))
    c3.metric('Available', int(num_available))

    st.markdown("---")
    st.subheader("🔍 Filters")

    c1, c2, c3 = st.columns(3)

    with c1:
        client_search = st.text_input('Client contains')

    with c2:
        start_filter = st.date_input('Start on/after', value=None)

    with c3:
        end_filter = st.date_input('End on/before', value=None)

    # APPLY FILTERS
    filtered = full.copy()

    if client_search:
        filtered = filtered[
            filtered['Client Name'].astype(str).str.contains(client_search, case=False, na=False)
        ]

    if start_filter:
        filtered = filtered[
            pd.to_datetime(filtered['Contract Start Date'], errors='coerce') >= pd.Timestamp(start_filter)
        ]

    if end_filter:
        filtered = filtered[
            pd.to_datetime(filtered['Contract End Date'], errors='coerce') <= pd.Timestamp(end_filter)
        ]

    st.write("### 📄 Filtered Results")
    st.dataframe(filtered)

    # SAVE filtered results for Print Tab
    st.session_state.summary_filtered = filtered


# -------------------- SAVED DATA --------------------
elif menu == 'Saved Data':

    st.header("📁 Saved Data (Archive)")

    st.dataframe(st.session_state.saved_df)

    c1, c2 = st.columns([1,1])

    # Export CSV
    with c1:
        if st.button("📤 Export CSV"):
            out = "SavedData_export.csv"
            st.session_state.saved_df.to_csv(out, index=False)
            st.success(f"✔ Exported to {out}")

    # Clear Archive
    with c2:
        if st.button("🧹 Clear Archive"):
            st.session_state.saved_df = pd.DataFrame(columns=st.session_state.saved_df.columns)
            if auto_save and use_sql:
                save_to_db(st.session_state.dashboard_df, st.session_state.summary_df, st.session_state.saved_df)
            st.success("✔ Archive cleared")
            st.rerun()

    st.markdown("---")
    st.subheader("↩ Undo rows back to Dashboard")

    for i in range(len(st.session_state.saved_df)):
        row = st.session_state.saved_df.iloc[i]
        cols = st.columns([4,1])

        with cols[0]:
            st.write(row.to_frame().T)

        with cols[1]:
            key = f"undo_{i}"
            if st.button("Undo → Dashboard", key=key):
                try:
                    col_bb = next((c for c in st.session_state.saved_df.columns if "billboard" in c.lower() or "number" in c.lower()), None)
                    if col_bb is None:
                        st.error("Billboard Number column not found!")
                        continue

                    bb_num = row[col_bb]
                    dash_idx = st.session_state.dashboard_df.index[
                        st.session_state.dashboard_df['Billboard Number'] == bb_num
                    ].tolist()

                    if not dash_idx:
                        st.error(f"Billboard {bb_num} not found in Dashboard")
                        continue

                    j = dash_idx[0]

                    for col in st.session_state.saved_df.columns:
                        if col != col_bb and col in st.session_state.dashboard_df.columns:
                            st.session_state.dashboard_df.at[j, col] = row[col]

                    # Remove from saved data
                    st.session_state.saved_df = st.session_state.saved_df.drop(index=i).reset_index(drop=True)

                    if auto_save and use_sql:
                        save_to_db(st.session_state.dashboard_df, st.session_state.summary_df, st.session_state.saved_df)

                    st.success(f"✔ Restored to Billboard {bb_num}")
                    st.rerun()

                except Exception as e:
                    st.error(f"Undo failed: {e}")


# -------------------- ADMIN --------------------
elif menu == 'Admin':

    st.header("⚙️ Admin — DB & System Controls")

    c1, c2, c3 = st.columns(3)

    # SAVE
    with c1:
        if st.button("💾 Save to SQLite"):
            if use_sql:
                save_to_db(st.session_state.dashboard_df, st.session_state.summary_df, st.session_state.saved_df)
                st.success("✔ Saved to DB")
            else:
                st.error("Enable SQLite persistence first!")

    # RELOAD
    with c2:
        if st.button("🔄 Reload from DB"):
            if use_sql and os.path.exists(DB_PATH):
                dash, summ, saved = read_sheets_sqlite()
                st.session_state.dashboard_df = dash
                st.session_state.saved_df = saved
                st.session_state.summary_df = summ
                st.success("✔ Reloaded")
                st.rerun()
            else:
                st.error("DB not found or SQLite off")

    # RESET DASHBOARD
    with c3:
        if st.button("🧨 Reset Dashboard (Empty 1..50)"):
            df = pd.DataFrame(columns=DEFAULT_COLS)
            if len(df) < MAX_BOARDS:
                extra = MAX_BOARDS - len(df)
                add_df = pd.DataFrame([[""]*len(df.columns)]*extra, columns=df.columns)
                df = pd.concat([df, add_df], ignore_index=True)

            df['Billboard Number'] = list(range(1, MAX_BOARDS+1))
            st.session_state.dashboard_df = df

            if auto_save and use_sql:
                save_to_db(st.session_state.dashboard_df, st.session_state.summary_df, st.session_state.saved_df)

            st.success("✔ Dashboard Reset")
            st.rerun()

    st.markdown("---")
    st.write("### 🔍 DB Info")
    st.write({
        "db_exists": os.path.exists(DB_PATH),
        "db_path": DB_PATH
    })
# -------------------- PRINT (UNIVERSAL PRINT PANEL) --------------------
elif menu == "Print":

    st.header("🖨️ Universal Print Panel")

    src = st.selectbox("Select Source", ["Dashboard", "Summary", "Saved Data"])

    # SOURCE LOAD
    if src == "Dashboard":
        source_df = st.session_state.dashboard_df.copy()

    elif src == "Summary":
        source_df = st.session_state.get("summary_filtered", pd.DataFrame())

    else:
        source_df = st.session_state.saved_df.copy()

    if source_df.empty:
        st.warning("⚠ No records available.")
        st.stop()

    bb_list = sorted(source_df["Billboard Number"].dropna().unique().tolist())
    selected_bb = st.selectbox("Billboard Number", bb_list)

    record_row = source_df[source_df["Billboard Number"] == selected_bb]

    if record_row.empty:
        st.error("❌ Record not found.")
        st.stop()

    record = record_row.iloc[0].to_dict()

    # CSS
    st.markdown("""
<style>
.form-card{background:#fff;padding:25px;border-radius:12px;width:90%;margin:auto;box-shadow:0 4px 10px rgba(0,0,0,0.1);}
.form-header{background:#1e40af;color:#fff;padding:12px;text-align:center;font-size:24px;border-radius:10px 10px 0 0;}
.form-table{width:100%;border-collapse:collapse;margin-top:15px;}
.form-table td{border:1px solid #d6d6d6;padding:9px;}
.label-cell{font-weight:600;background:#f3f4f6;}
.print-btn{background:#2563eb;color:white;padding:6px 16px;border-radius:6px;border:none;margin-top:10px;}
.print-btn:hover{background:#1d4ed8;}
.print-footer{display:flex;justify-content:space-between;margin-top:10px;color:#555;}
</style>
""", unsafe_allow_html=True)

    # HTML (IMPORTANT: NO INDENT)
    html_content = f"""
<div class="form-card">
<div class="form-header">Billboard Contract Form</div>

<table class="form-table">
<tr><td class="label-cell">Billboard Number</td><td>{record.get('Billboard Number','—')}</td></tr>
<tr><td class="label-cell">Client Name</td><td>{record.get('Client Name','—')}</td></tr>
<tr><td class="label-cell">Company Name</td><td>{record.get('Company Name','—')}</td></tr>
<tr><td class="label-cell">Location</td><td>{record.get('Location','—')}</td></tr>
<tr><td class="label-cell">Billboard Size</td><td>{record.get('Billboard Size','—')}</td></tr>
<tr><td class="label-cell">Start Date</td><td>{record.get('Contract Start Date','—')}</td></tr>
<tr><td class="label-cell">End Date</td><td>{record.get('Contract End Date','—')}</td></tr>
<tr><td class="label-cell">Rent Amount (PKR)</td><td>{record.get('Rent Amount (PKR)','—')}</td></tr>
<tr><td class="label-cell">Advance Received (PKR)</td><td>{record.get('Advance Received (PKR)','—')}</td></tr>
<tr><td class="label-cell">Balance (PKR)</td><td>{record.get('Balance / Credit (PKR)','—')}</td></tr>
<tr><td class="label-cell">Payment Status</td><td>{record.get('Payment Status','—')}</td></tr>
<tr><td class="label-cell">Contract Status</td><td>{record.get('Contract Status','—')}</td></tr>
<tr><td class="label-cell">Remarks</td><td>{record.get('Remarks / Notes','—')}</td></tr>
</table>

<div class="print-footer">
<span>Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M')}</span>
<button onclick="window.print()" class="print-btn">Print</button>
</div>
</div>
"""

    # PREVIEW
    st.markdown(html_content, unsafe_allow_html=True)

    # PDF EXPORT
    pdf_bytes = pdfkit.from_string(
        html_content,
        False,
        configuration=pdf_config
    )

    st.download_button(
        label="⬇ Download PDF",
        data=pdf_bytes,
        file_name=f"Billboard_{selected_bb}_Contract.pdf",
        mime="application/pdf"
    )
