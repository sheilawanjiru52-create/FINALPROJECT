
import streamlit as st
import pandas as pd
import sqlite3
import hashlib
import secrets
from pathlib import Path
import json
from datetime import date
from sklearn.preprocessing import StandardScaler
from sklearn.cluster import KMeans

if "auth_page" not in st.session_state:
    st.session_state["auth_page"] = "Register"
    
# Database location: same folder as app.py
DB_PATH = Path(__file__).parent / "nutrition_app.db"


def get_connection():
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def create_food_entries_table():
    with get_connection() as connection:
        # Check which columns already exist
        columns = {
            row["name"]
            for row in connection.execute(
                "PRAGMA table_info(food_entries)"
            ).fetchall()
        }

        # Add missing columns without deleting existing records
        if "eaten_date" not in columns:
            connection.execute(
                "ALTER TABLE food_entries ADD COLUMN eaten_date TEXT"
            )

        if "nutrients_json" not in columns:
            connection.execute(
                "ALTER TABLE food_entries ADD COLUMN nutrients_json TEXT"
            )

        # Copy the date from the existing eaten_at column
        if "eaten_at" in columns:
            connection.execute("""
                UPDATE food_entries
                SET eaten_date = substr(eaten_at, 1, 10)
                WHERE eaten_date IS NULL
                  AND eaten_at IS NOT NULL
            """)


def hash_password(password, salt=None):
    """Hash a password rather than saving it as plain text."""
    if salt is None:
        salt = secrets.token_hex(16)

    password_hash = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("utf-8"),
        600_000
    ).hex()

    return password_hash, salt


def register_user(
    name, email, password, age,
    sex=None, height_cm=None, weight_kg=None,
    activity_level=None
):
    password_hash, salt = hash_password(password)

    try:
        with get_connection() as connection:
            connection.execute(
                """
                INSERT INTO users (
                    name, email, password_hash, password_salt,
                    age, sex, height_cm, weight_kg, activity_level
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    name.strip(),
                    email.strip().lower(),
                    password_hash,
                    salt,
                    age,
                    sex,
                    height_cm,
                    weight_kg,
                    activity_level
                )
            )
        return True, "Account created successfully!"

    except sqlite3.IntegrityError:
        return False, "This email may already be registered. Try logging in."


def authenticate_user(email, password):
    with get_connection() as connection:
        user = connection.execute(
            "SELECT * FROM users WHERE email = ?",
            (email.strip().lower(),)
        ).fetchone()

    if user is None:
        return None

    calculated_hash, _ = hash_password(
        password, salt=user["password_salt"]
    )

    if secrets.compare_digest(
        calculated_hash, user["password_hash"]
    ):
        return user

    return None


def show_auth_page():
    st.title("🥗 Welcome to NutriTrack")
    st.write("Create an account or log in to track your nutrition.")

    # Always show a visible choice
    auth_choice = st.radio(
        "Choose an option",
        ["Register", "Log In"],
        horizontal=True,
        key="auth_choice"
    )

    if auth_choice == "Register":
        st.subheader("Create your account")

        with st.form("registration_form"):
            st.markdown("#### Personal information")

            st.markdown("**What is your full name?**")
            name = st.text_input(
                "Full name", placeholder="Enter your full name",
                label_visibility="collapsed"
            )

            st.markdown("**How old are you?**")
            age = st.number_input(
                "Age", min_value=1, max_value=120, value=None,
                placeholder="Enter your age",
                label_visibility="collapsed"
            )

            st.markdown("**What is your sex? (Optional)**")
            sex = st.selectbox(
                "Sex", ["Prefer not to say", "Female", "Male", "Other"],
                label_visibility="collapsed"
            )

            st.markdown("**What is your height in centimetres? (Optional)**")
            height = st.number_input(
                "Height", min_value=0.0, max_value=250.0, value=0.0,
                label_visibility="collapsed"
            )

            st.markdown("**What is your weight in kilograms? (Optional)**")
            weight = st.number_input(
                "Weight", min_value=0.0, max_value=400.0, value=0.0,
                label_visibility="collapsed"
            )

            st.markdown("**What is your activity level? (Optional)**")
            activity = st.selectbox(
                "Activity level",
                [
                    "Not specified", "Sedentary", "Lightly active",
                    "Moderately active", "Very active", "Extra active"
                ],
                label_visibility="collapsed"
            )

            st.markdown("#### Account information")

            st.markdown("**What is your email address?**")
            email = st.text_input(
                "Email", placeholder="Enter your email address",
                label_visibility="collapsed"
            )

            st.markdown("**Create a password (at least 8 characters)**")
            password = st.text_input(
                "Password", type="password",
                label_visibility="collapsed"
            )

            st.markdown("**Confirm your password**")
            confirm_password = st.text_input(
                "Confirm password", type="password",
                label_visibility="collapsed"
            )

            submitted = st.form_submit_button(
                "Create My Account", use_container_width=True
            )

        if submitted:
            if not name.strip() or not email.strip() or not password:
                st.error("Please enter your name, email, and password.")
            elif age is None:
                st.error("Please enter your age.")
            elif "@" not in email or "." not in email.split("@")[-1]:
                st.error("Please enter a valid email address.")
            elif len(password) < 8:
                st.error("Your password must be at least 8 characters.")
            elif password != confirm_password:
                st.error("Your passwords do not match.")
            else:
                success, message = register_user(
                    name=name,
                    email=email,
                    password=password,
                    age=int(age),
                    sex=None if sex == "Prefer not to say" else sex,
                    height_cm=height if height > 0 else None,
                    weight_kg=weight if weight > 0 else None,
                    activity_level=(
                        None if activity == "Not specified" else activity
                    )
                )

                if success:
                    st.session_state["auth_choice"] = "Log In"
                    st.success("Account created! Select Log In above.")
                    st.rerun()
                else:
                    st.error(message)

    else:
        st.subheader("Log in to your account")

        with st.form("login_form"):
            st.markdown("**What is your email address?**")
            login_email = st.text_input(
                "Email", key="login_email",
                placeholder="Enter your registered email",
                label_visibility="collapsed"
            )

            st.markdown("**What is your password?**")
            login_password = st.text_input(
                "Password", type="password", key="login_password",
                label_visibility="collapsed"
            )

            login_submitted = st.form_submit_button(
                "Log In", use_container_width=True
            )

        if login_submitted:
            user = authenticate_user(login_email, login_password)

            if user is not None:
                st.session_state["user_id"] = user["user_id"]
                st.session_state["user_name"] = user["name"]
                st.rerun()
            else:
                st.error("Incorrect email or password.")

# ---------------------------------------
# 1. PAGE CONFIGURATION
# ---------------------------------------

st.set_page_config(
    page_title="NutriTrack | Nutrition Tracker",
    page_icon="🥗",
    layout="wide"
)

# ---------------------------------------
# 2. CUSTOM INTERFACE STYLING
# ---------------------------------------

st.markdown("""

<style>
    /* Main application background */
    .stApp {
        background-color: #F6F8F5;
        color: #222222;
    }

    /* Sidebar */
    [data-testid="stSidebar"] {
        background-color: #173F35;
    }

    [data-testid="stSidebar"] * {
        color: #ffffff;
    }

    /* Main headings */
    .main-title {
        font-size: 36px;
        font-weight: 750;
        color: #173F35 !important;
        margin-bottom: 0;
    }

    .subtitle {
        color: #66756D !important;
        font-size: 16px;
        margin-bottom: 25px;
    }

    /* Nutrient cards */
    .nutrient-card {
        background-color: #ffffff;
        border: 1px solid #E1E8E2;
        border-radius: 14px;
        padding: 18px;
        margin-bottom: 12px;
    }

    .nutrient-name {
        color: #66756D !important;
        font-size: 14px;
    }

    .nutrient-value {
        color: #173F35 !important;
        font-size: 27px;
        font-weight: 700;
        margin-top: 5px;
    }

    /* Buttons */
    div.stButton > button {
        background-color: #236B50;
        color: #ffffff !important;
        border-radius: 9px;
        border: none;
        min-height: 45px;
        font-weight: 600;
    }

    div.stButton > button:hover {
        background-color: #174B39;
        color: #ffffff !important;
    }

    /* Main-page text, headings and descriptions */
    .stApp .main .stMarkdown,
    .stApp .main .stMarkdown p,
    .stApp .main .stMarkdown span,
    .stApp .main .stMarkdown li,
    .stApp .main .stMarkdown strong,
    .stApp .main .stMarkdown h1,
    .stApp .main .stMarkdown h2,
    .stApp .main .stMarkdown h3 {
        color: #222222 !important;
        opacity: 1 !important;
    }

    /* Form questions and widget labels */
    [data-testid="stWidgetLabel"],
    [data-testid="stWidgetLabel"] *,
    .stRadio label,
    .stRadio label p,
    .stCheckbox label,
    .stCheckbox label p {
        color: #222222 !important;
        opacity: 1 !important;
    }

    /* Text input fields */
    .stTextInput input,
    .stNumberInput input,
    .stDateInput input,
    .stTextArea textarea {
        color: #222222 !important;
        background-color: #ffffff !important;
        -webkit-text-fill-color: #222222 !important;
        opacity: 1 !important;
    }

    /* Input placeholders */
    .stTextInput input::placeholder,
    .stNumberInput input::placeholder,
    .stTextArea textarea::placeholder {
        color: #66756D !important;
        -webkit-text-fill-color: #66756D !important;
        opacity: 1 !important;
    }

    /* Dropdowns */
    .stSelectbox [data-baseweb="select"] {
        color: #222222 !important;
        background-color: #ffffff !important;
    }

    .stSelectbox [data-baseweb="select"] * {
        color: #222222 !important;
    }

    /* Selected dropdown value */
    .stSelectbox input {
        color: #222222 !important;
        -webkit-text-fill-color: #222222 !important;
    }

    /* Radio options */
    .stRadio [role="radiogroup"] label,
    .stRadio [role="radiogroup"] label p {
        color: #222222 !important;
    }

    /* Links */
    .stApp .main a {
        color: #236B50 !important;
    }
</style>

""", unsafe_allow_html=True)


# ---------------------------------------
# 3. LOAD DATA
# ---------------------------------------

@st.cache_data
def load_data():
    return pd.read_csv("food_composition_with_clusters.csv")

try:
    df = load_data()
except FileNotFoundError:
    st.error(
        "Could not find food_composition_with_clusters.csv. "
        "Place it in the same folder as app.py."
    )
    st.stop()

if "Food Name" not in df.columns:
    st.error("The dataset must contain a Food Name column.")
    st.stop()


# ---------------------------------------
# CLASSIFY FOOD TYPES
# ---------------------------------------

if "Section" not in df.columns:
    st.error("The dataset must contain a Section column.")
    st.stop()

df["Food Type"] = "Single-ingredient foods"

mixed_mask = (
    df["Section"]
    .fillna("")
    .astype(str)
    .str.strip()
    .str.lower()
    .str.contains("mixed dish", regex=False)
)

df.loc[mixed_mask, "Food Type"] = "Mixed foods"



# ---------------------------------------
# CLASSIFY FOOD TYPES
# ---------------------------------------

if "Section" not in df.columns:
    st.error("The dataset must contain a Section column.")
    st.stop()

df["Food Type"] = df["Section"].apply(
    lambda section: (
        "Mixed foods"
        if pd.notna(section)
        and "mixed dish" in str(section).strip().lower()
        else "Single-ingredient foods"
    )
)


# ---------------------------------------
# 4. NUTRIENT UNITS
# ---------------------------------------

nutrient_units = {
    "Energy (kcal)": ("Energy", "kcal"),
    "Energy (kJ)": ("Energy", "kJ"),
    "Protein (g)": ("Protein", "g"),
    "Fat (g)": ("Fat", "g"),
    "Carbohydrate available (g)": ("Carbohydrates", "g"),
    "Fibre (g)": ("Fibre", "g"),
    "Water (g)": ("Water", "g"),
    "Ash (g)": ("Ash", "g"),
    "Calcium (mg)": ("Calcium", "mg"),
    "Iron (mg)": ("Iron", "mg"),
    "Magnesium (mg)": ("Magnesium", "mg"),
    "Phosphorus (mg)": ("Phosphorus", "mg"),
    "Potassium (mg)": ("Potassium", "mg"),
    "Sodium (mg)": ("Sodium", "mg"),
    "Zinc (mg)": ("Zinc", "mg"),
    "Selenium (mcg)": ("Selenium", "mcg"),
    "Vitamin A RAE (mcg)": ("Vitamin A (RAE)", "mcg"),
    "Thiamin (mg)": ("Thiamin (B1)", "mg"),
    "Riboflavin (mg)": ("Riboflavin (B2)", "mg"),
    "Niacin (mg)": ("Niacin (B3)", "mg"),
    "Vitamin B12 (mcg)": ("Vitamin B12", "mcg"),
    "Vitamin C (mg)": ("Vitamin C", "mg"),
}

# ---------------------------------------
# 5. AUTHENTICATION CHECK
# ---------------------------------------

if "user_id" not in st.session_state:
    show_auth_page()

else:
    # Logged-in user's information
    st.sidebar.write(
        f"Logged in as: {st.session_state['user_name']}"
    )

    if st.sidebar.button("Log Out"):
        del st.session_state["user_id"]
        del st.session_state["user_name"]
        st.rerun()

    # ---------------------------------------
    # 6. SIDEBAR
    # ---------------------------------------

    with st.sidebar:
        st.markdown("# 🥗 NutriTrack")
        st.caption("PERSONAL NUTRITION TRACKER")
        st.divider()

        page = st.radio(
            "NAVIGATION",
            ["Food Tracker", "About the App"]
        )

        st.divider()
        st.caption("Food composition data powered by your dataset.")
        st.caption("K-means clustering supports food similarity insights.")

    # ---------------------------------------
    # 7. FOOD TRACKER AND ABOUT PAGE
    # ---------------------------------------

        # Inside the login check's else block

    
    
    if page == "Food Tracker":

        st.markdown(
            '<p class="main-title">Nutrition Dashboard</p>',
            unsafe_allow_html=True
        )
        st.write("Record your meals and monitor your nutrient intake.")

        # Create the food diary table if it does not exist
        create_food_entries_table()

        user_id = st.session_state["user_id"]

        # Identify the food-code column in the dataset
        code_column = next(
            (c for c in ["Food Code", "Code", "Food_Code"]
            if c in df.columns),
            None
        )

        # Use the nutrient columns available in the dataset
        available_nutrients = {
            col: nutrient_units[col]
            for col in nutrient_units
            if col in df.columns
        }

        if not available_nutrients:
            st.error("No supported nutrient columns were found.")
            st.stop()

        # ---------------------------------------
        # FOOD ENTRY FORM
        # ---------------------------------------

        st.subheader("Add a Food Entry")

                # Create food category filter
        food_type_options = [
            "All foods",
            "Single-ingredient foods",
            "Mixed foods"
        ]

                # Create food category filter
        selected_food_type = st.selectbox(
            "Choose food category",
            [
                "All foods",
                "Single-ingredient foods",
                "Mixed foods"
            ],
            key="food_type_filter"
        )

        # Filter foods according to the selected category
        if selected_food_type == "All foods":
            filtered_df = df.copy()
        else:
            filtered_df = df[
                df["Food Type"].astype(str).str.strip()
                == selected_food_type
            ].copy()

        food_names = sorted(
            filtered_df["Food Name"]
            .dropna()
            .astype(str)
            .unique()
            .tolist()
        )

        if not food_names:
            st.warning(
                f"No foods found for category: {selected_food_type}"
            )
            st.stop()

        # Food entry form
        with st.form("food_entry_form"):

            selected_food = st.selectbox(
                "Search and select a food",
                food_names,
                key="food_selector"
            )

            col1, col2, col3 = st.columns(3)

            with col1:
                quantity = st.number_input(
                    "Quantity eaten (grams)",
                    min_value=1.0,
                    max_value=5000.0,
                    value=100.0,
                    step=10.0
                )

            with col2:
                meal_type = st.selectbox(
                    "Meal",
                    ["Breakfast", "Lunch", "Dinner", "Snack"]
                )

            with col3:
                eaten_date = st.date_input(
                    "Date eaten",
                    value=date.today()
                )

            submitted = st.form_submit_button(
                "Save Food Entry",
                use_container_width=True
            )

        # ---------------------------------------
        # CALCULATE AND SAVE NUTRIENTS
        # ---------------------------------------

        if submitted:

            selected_row = df.loc[
                df["Food Name"].astype(str) == selected_food
            ].iloc[0]

            # Nutrient data in the CSV is per 100 g.
            # Blank or non-numeric values remain unknown.
            nutrient_totals = {}

            for column in available_nutrients:

                raw_value = selected_row[column]
                numeric_value = pd.to_numeric(
                    pd.Series([raw_value]),
                    errors="coerce"
                ).iloc[0]

                if pd.isna(numeric_value):
                    nutrient_totals[column] = None
                else:
                    nutrient_totals[column] = round(
                        float(numeric_value) * quantity / 100,
                        4
                    )

            food_code = (
                str(selected_row[code_column])
                if code_column is not None
                and pd.notna(selected_row[code_column])
                else None
            )

        
            

            nutrients_json = json.dumps(nutrient_totals)

            with get_connection() as connection:
                connection.execute(
                    """
                    INSERT INTO food_entries (
                        user_id,
                        food_code,
                        food_name,
                        quantity_g,
                        meal_type,
                        eaten_at,
                        eaten_date,
                        nutrients_json
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        user_id,
                        food_code,
                        selected_food,
                        quantity,
                        meal_type,
                        eaten_date.isoformat(),
                        eaten_date.isoformat(),
                        nutrients_json
                    )
                )



            st.success(
                f"Saved {quantity:g} g of {selected_food} "
                f"for {meal_type.lower()}."
            )

            st.rerun()

        # ---------------------------------------
        # SELECT THE DAY TO REVIEW
        # ---------------------------------------

        st.divider()
        st.subheader("Daily Nutrition Summary")

        summary_date = st.date_input(
            "View food entries for",
            value=date.today(),
            key="summary_date"
        )

        with get_connection() as connection:
            entries = pd.read_sql_query(
                """
                SELECT entry_id, food_name, quantity_g,
                    meal_type, eaten_date, nutrients_json
                FROM food_entries
                WHERE user_id = ? AND eaten_date = ?
                ORDER BY entry_id DESC
                """,
                connection,
                params=(user_id, summary_date.isoformat())
            )

        # ---------------------------------------
        # DAILY TOTALS
        # ---------------------------------------

        if entries.empty:

            st.info(
                "No food entries recorded for this date yet. "
                "Use the form above to add your first meal."
            )

        else:

            # Sum known nutrient values. Unknown values are not
            # interpreted as zero in the displayed food records.
            totals = {}

            for column in available_nutrients:
                values = []

                for nutrient_json in entries["nutrients_json"]:
                    saved_nutrients = json.loads(nutrient_json)
                    value = saved_nutrients.get(column)

                    if value is not None:
                        values.append(float(value))

                totals[column] = sum(values) if values else None

            energy_col = next(
                (c for c in ["Energy (kcal)", "Energy (kJ)"]
                if c in available_nutrients),
                None
            )

            protein_col = "Protein (g)"
            fat_col = "Fat (g)"
            carb_col = "Carbohydrate available (g)"

            def format_total(column):
                value = totals.get(column)
                if value is None:
                    return "Unknown"
                unit = nutrient_units[column][1]
                return f"{value:.1f} {unit}"

            c1, c2, c3, c4 = st.columns(4)

            with c1:
                st.metric(
                    "Energy",
                    format_total(energy_col)
                    if energy_col else "Unavailable"
                )

            with c2:
                st.metric("Protein", format_total(protein_col))

            with c3:
                st.metric("Carbohydrates", format_total(carb_col))

            with c4:
                st.metric("Fat", format_total(fat_col))

            st.caption(
                "Daily totals add the known nutrient values from saved "
                "entries. Unknown nutrient values are excluded, so totals "
                "may be incomplete."
            )

            # ---------------------------------------
            # FOOD DIARY
            # ---------------------------------------

            st.subheader("Your Food Diary")

            diary = entries[
                ["food_name", "quantity_g", "meal_type"]
            ].copy()

            diary.columns = ["Food", "Quantity (g)", "Meal"]

            st.dataframe(
                diary,
                use_container_width=True,
                hide_index=True
            )

            # ---------------------------------------
            # NUTRIENT BREAKDOWN
            # ---------------------------------------

            with st.expander("View all available daily nutrients"):

                nutrient_rows = []

                for column, (display_name, unit) in available_nutrients.items():
                    value = totals[column]

                    nutrient_rows.append({
                        "Nutrient": display_name,
                        "Daily total": (
                            round(value, 2)
                            if value is not None
                            else "Unknown"
                        ),
                        "Unit": unit
                    })

                st.dataframe(
                    pd.DataFrame(nutrient_rows),
                    use_container_width=True,
                    hide_index=True
                )

        
        # ---------------------------------------
        # K-MEANS NUTRITION-GOAL RECOMMENDATIONS
        # ---------------------------------------

        st.divider()
        st.subheader("Food Recommendations")
        st.write(
            "Choose a nutrition goal to discover foods "
            "that match your preferences."
        )

        goal = st.selectbox(
            "Choose your nutrition goal",
            [
                "Higher protein",
                "Higher fibre",
                "Lower energy",
                "Specific Nutrient",
            ],
            key="nutrition_goal"
        )

        # Map the ready-made goals to dataset columns.
        goal_columns = {
            "Higher protein": "Protein (g)",
            "Higher fibre": "Fibre (g)",
            "Lower energy": "Energy (kcal)",
        }

        if goal == "Specific Nutrient":

            # Use nutrient columns that exist in the dataset.
            specific_nutrients = {
                col: details[0]
                for col, details in nutrient_units.items()
                if col in df.columns
            }

            if not specific_nutrients:
                st.warning(
                    "No supported nutrients are available."
                )

            else:
                selected_nutrient = st.selectbox(
                    "Select a specific nutrient",
                    list(specific_nutrients.keys()),
                    format_func=lambda col: specific_nutrients[col],
                    key="specific_nutrient"
                )

                direction = st.radio(
                    "Recommend foods with",
                    ["Highest amount", "Lowest amount"],
                    horizontal=True,
                    key="specific_nutrient_direction"
                )

                target_column = selected_nutrient
                ascending_order = direction == "Lowest amount"

                if "KMeans_Cluster" not in df.columns:
                    st.warning(
                        "K-Means cluster labels were not found."
                    )
                else:
                    recommendation_data = df[
                        ["Food Name", "KMeans_Cluster", target_column]
                    ].copy()

                    recommendation_data[target_column] = pd.to_numeric(
                        recommendation_data[target_column],
                        errors="coerce"
                    )

                    recommendation_data = recommendation_data.dropna(
                        subset=[
                            "Food Name",
                            "KMeans_Cluster",
                            target_column
                        ]
                    )

                    if recommendation_data.empty:
                        st.info(
                            "No foods have known values for this nutrient."
                        )
                    else:
                        cluster_means = recommendation_data.groupby(
                            "KMeans_Cluster"
                        )[target_column].mean()

                        recommended_cluster = (
                            cluster_means.idxmin()
                            if ascending_order
                            else cluster_means.idxmax()
                        )

                        recommendations = recommendation_data[
                            recommendation_data["KMeans_Cluster"]
                            == recommended_cluster
                        ].sort_values(
                            target_column,
                            ascending=ascending_order
                        ).head(10)

                        st.caption(
                            f"Recommended cluster: {recommended_cluster}"
                        )

                        st.dataframe(
                            recommendations.rename(
                                columns={
                                    "Food Name": "Food",
                                    "KMeans_Cluster": "Cluster",
                                    target_column: (
                                        f"{specific_nutrients[target_column]} "
                                        "per 100 g"
                                    ),
                                }
                            ).round(2),
                            use_container_width=True,
                            hide_index=True
                        )

        else:
            target_column = goal_columns[goal]

            if target_column not in df.columns:
                st.warning(
                    f"The dataset does not contain {target_column}."
                )

            elif "KMeans_Cluster" not in df.columns:
                st.warning(
                    "K-Means cluster labels were not found."
                )

            else:
                recommendation_data = df[
                    ["Food Name", "KMeans_Cluster", target_column]
                ].copy()

                recommendation_data[target_column] = pd.to_numeric(
                    recommendation_data[target_column],
                    errors="coerce"
                )

                recommendation_data = recommendation_data.dropna(
                    subset=[
                        "Food Name",
                        "KMeans_Cluster",
                        target_column
                    ]
                )

                if recommendation_data.empty:
                    st.info(
                        "No foods have known values for this nutrient."
                    )

                else:
                    ascending_order = goal == "Lower energy"

                    cluster_means = recommendation_data.groupby(
                        "KMeans_Cluster"
                    )[target_column].mean()

                    recommended_cluster = (
                        cluster_means.idxmin()
                        if ascending_order
                        else cluster_means.idxmax()
                    )

                    recommendations = recommendation_data[
                        recommendation_data["KMeans_Cluster"]
                        == recommended_cluster
                    ].sort_values(
                        target_column,
                        ascending=ascending_order
                    ).head(10)

                    st.caption(
                        f"Recommended cluster: {recommended_cluster}"
                    )

                    st.dataframe(
                        recommendations.rename(
                            columns={
                                "Food Name": "Food",
                                "KMeans_Cluster": "Cluster",
                                target_column: f"{target_column} per 100 g",
                            }
                        ).round(2),
                        use_container_width=True,
                        hide_index=True
                    )

        st.caption(
            "Nutrient values are per 100 g of food. Unknown nutrient "
            "values are excluded from recommendations."
        )



    elif page == "About the App":

        st.markdown(
            '<p class="main-title">About NutriTrack</p>',
            unsafe_allow_html=True
        )

        st.write(
            "NutriTrack is a nutrition tracking application designed "
            "to help users record food intake and understand their "
            "nutrient consumption."
        )

        st.subheader("Key Features")

        st.markdown("""
        - **Food tracking:** Record foods consumed throughout the day.
        - **Nutrient analysis:** Explore calories, protein, fats,
        carbohydrates, vitamins and minerals.
        - **Nutrition summaries:** Review dietary patterns over time.
        - **Food composition database:** Explore individual foods
        and mixed dishes.
        - **User accounts:** Keep food-entry histories separate
        for different users.
        """)
