import streamlit as st
import pandas as pd
import sqlite3
import hashlib
import secrets
from pathlib import Path
import json
from datetime import date, datetime, timedelta
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


def create_nutrition_targets_table():
    """Store per-user daily targets without changing existing food records."""
    with get_connection() as connection:
        connection.execute("""
            CREATE TABLE IF NOT EXISTS user_nutrition_targets (
                user_id INTEGER NOT NULL,
                nutrient TEXT NOT NULL,
                target_value REAL NOT NULL,
                target_mode TEXT NOT NULL DEFAULT 'Manual',
                updated_at TEXT NOT NULL,
                PRIMARY KEY (user_id, nutrient),
                FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
            )
        """)


def create_health_preferences_table():
    """Store optional health and menstrual-nutrition preferences per user."""
    with get_connection() as connection:
        connection.execute("""
            CREATE TABLE IF NOT EXISTS user_health_preferences (
                user_id INTEGER PRIMARY KEY,
                conditions_json TEXT NOT NULL DEFAULT '[]',
                menstrual_nutrition TEXT NOT NULL DEFAULT 'No',
                updated_at TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
            )
        """)


def estimate_daily_targets(profile):
    """Estimate energy using Mifflin-St Jeor and protein at 0.8 g/kg/day."""
    if profile is None:
        return {}
    try:
        age = float(profile['age'])
        height = float(profile['height_cm'])
        weight = float(profile['weight_kg'])
        sex = profile['sex']
        activity = profile['activity_level']
    except (TypeError, ValueError, IndexError):
        return {}
    if age <= 0 or height <= 0 or weight <= 0 or sex not in ('Female', 'Male'):
        return {}
    activity_factors = {
        'Sedentary': 1.2,
        'Lightly active': 1.375,
        'Moderately active': 1.55,
        'Very active': 1.725,
        'Extra active': 1.9,
    }
    if activity not in activity_factors:
        return {}
    # Mifflin-St Jeor resting energy equation, then activity multiplier.
    sex_adjustment = -161 if sex == 'Female' else 5
    resting = (10 * weight) + (6.25 * height) - (5 * age) + sex_adjustment
    energy_kcal = max(0, resting * activity_factors[activity])
    return {
        'Energy (kcal)': round(energy_kcal),
        'Protein (g)': round(weight * 0.8, 1),
    }


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
    
     # Switch to Log In before creating the radio widget
    if st.session_state.get("switch_to_login", False):
        st.session_state["auth_choice"] = "Log In"
        st.session_state["switch_to_login"] = False

    
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
                    st.session_state["switch_to_login"] = True
                    st.success("Account created! Switching to Log In...")
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
    
    /* Make metric cards readable on the light background */
    [data-testid="stMetricLabel"] {
        color: #173F35 !important;
    }

    [data-testid="stMetricValue"] {
        color: #173F35 !important;
    }

    [data-testid="stMetricDelta"] {
        color: #66756D !important;
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

# ---------------------------------------
# CLASSIFY FOOD TYPES
# ---------------------------------------

if "Section" not in df.columns:
    st.error("The dataset must contain a Section column.")
    st.stop()

# The dataset's actual section label is "Mixed Dishes".
df["Food Type"] = df["Section"].apply(
    lambda section: (
        "Mixed Dishes"
        if pd.notna(section)
        and "mixed dish" in str(section).strip().lower()
        else "Single-ingredient foods"
    )
)


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
            [
                "Nutrition Dashboard",
                "Food Tracker",
                "Daily Nutrition Summary",
                "Nutrition Trends",
                "Nutrition Targets",
                "Health Profile",
                "Food Recommendations",
                "About the App"
            ],
            key="main_navigation"
        )


        st.divider()
        st.caption("Food composition data powered by your dataset.")
        st.caption("K-means clustering supports food similarity insights.")

    
    # ---------------------------------------
    # SHARED SETUP FOR LOGGED-IN PAGES
    # ---------------------------------------

    create_food_entries_table()
    create_nutrition_targets_table()
    create_health_preferences_table()
    user_id = st.session_state["user_id"]

    available_nutrients = {
        col: nutrient_units[col]
        for col in nutrient_units
        if col in df.columns
    }

    if not available_nutrients:
        st.error("No supported nutrient columns were found.")
        st.stop()

    # ---------------------------------------
    # 7. FOOD TRACKER AND ABOUT PAGE
    # ---------------------------------------

        # Inside the login check's else block

    if page == "Nutrition Dashboard":
        st.markdown(
            '<p class="main-title">Nutrition Dashboard</p>',
            unsafe_allow_html=True
        )
        st.write(
            "Welcome to NutriTrack. Use the navigation menu to record meals, "
            "review your daily nutrient intake, and explore food recommendations."
        )
        st.markdown("### Get started")
        st.write("- **Food Tracker:** add foods, quantities, meal types, and eating times.")
        st.write("- **Daily Nutrition Summary:** review your entries and nutrient totals by date.")
        st.write("- **Food Recommendations:** explore foods using your K-Means clusters.")

        with get_connection() as connection:
            count_row = connection.execute(
                "SELECT COUNT(*) AS entry_count FROM food_entries WHERE user_id = ?",
                (user_id,)
            ).fetchone()

            # Retrieve profile details from the existing users table.
            # This is read-only and does not alter existing account data.
            profile = connection.execute(
                """
                SELECT name, age, sex, height_cm, weight_kg, activity_level
                FROM users
                WHERE user_id = ?
                """,
                (user_id,)
            ).fetchone()

        st.metric("Food entries recorded", int(count_row["entry_count"]))

        st.markdown("### Your Profile")
        st.caption(
            "These details are read from your registered account. "
            "Optional information may be blank if it was not provided or saved."
        )

        if profile is None:
            st.warning(
                "We could not find your profile in the users table. "
                "Please log out and log in again, and contact support if this continues."
            )
        else:
            profile_cols = st.columns(3)

            def display_profile_value(value, suffix=""):
                if value is None or (isinstance(value, str) and not value.strip()):
                    return "Not provided"
                if isinstance(value, (int, float)) and value == 0:
                    return "Not provided"
                return f"{value}{suffix}"

            profile_cols[0].metric("Age", display_profile_value(profile["age"], " years"))
            profile_cols[1].metric("Sex", display_profile_value(profile["sex"]))
            profile_cols[2].metric(
                "Height", display_profile_value(profile["height_cm"], " cm")
            )
            profile_cols[0].metric(
                "Weight", display_profile_value(profile["weight_kg"], " kg")
            )
            profile_cols[1].metric(
                "Activity level", display_profile_value(profile["activity_level"])
            )
            st.info(
                "We are checking that your profile details are saved correctly. "
                "Personalized daily nutrition targets will be added after this verification."
            )

    elif page == "Food Tracker":


        st.markdown(
            '<p class="main-title">Food Tracker</p>',
            unsafe_allow_html=True
        )
        st.write("Record your meals and monitor your nutrient intake.")


        # Identify the food-code column in the dataset
        code_column = next(
            (c for c in ["Food Code", "Code", "Food_Code"]
            if c in df.columns),
            None
        )


        # ---------------------------------------
        # FOOD ENTRY FORM
        # ---------------------------------------

        st.subheader("Add a Food Entry")

                
        # Select a food category
        selected_food_type = st.selectbox(
            "Choose food category",
            [
                "All foods",
                "Single-ingredient foods",
                "Mixed Dishes"
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

            eaten_time = st.time_input(
                "Time eaten",
                value=datetime.now().time().replace(
                    second=0,
                    microsecond=0
                )
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
                        datetime.combine(
                            eaten_date,
                            eaten_time
                        ).isoformat(),
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

    elif page == "Daily Nutrition Summary":
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
                SELECT
                    entry_id,
                    food_name,
                    quantity_g,
                    meal_type,
                    eaten_at,
                    eaten_date,
                    nutrients_json
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
            # MEAL-BY-MEAL NUTRITION SUMMARY
            # ---------------------------------------

            st.subheader("Nutrition by Meal")

            meal_order = ["Breakfast", "Lunch", "Dinner", "Snack"]

            def calculate_meal_totals(meal_entries):
                meal_totals = {}

                for column in available_nutrients:
                    known_values = []

                    for nutrient_json in meal_entries["nutrients_json"]:
                        try:
                            saved_nutrients = json.loads(nutrient_json)
                        except (TypeError, json.JSONDecodeError):
                            continue

                        value = saved_nutrients.get(column)

                        if value is not None:
                            try:
                                known_values.append(float(value))
                            except (TypeError, ValueError):
                                continue

                    meal_totals[column] = (
                        sum(known_values) if known_values else None
                    )

                return meal_totals

            for meal in meal_order:
                meal_entries = entries[
                    entries["meal_type"].astype(str).str.strip().str.lower()
                    == meal.lower()
                ]

                with st.expander(
                    f"{meal} ({len(meal_entries)} food entries)",
                    expanded=False
                ):
                    if meal_entries.empty:
                        st.info(f"No {meal.lower()} entries for this date.")
                        continue

                    meal_totals = calculate_meal_totals(meal_entries)

                    energy_value = meal_totals.get("Energy (kcal)")
                    protein_value = meal_totals.get("Protein (g)")

                    metric1, metric2 = st.columns(2)

                    with metric1:
                        st.metric(
                            "Energy",
                            f"{energy_value:.1f} kcal"
                            if energy_value is not None
                            else "Unknown"
                        )

                    with metric2:
                        st.metric(
                            "Protein",
                            f"{protein_value:.1f} g"
                            if protein_value is not None
                            else "Unknown"
                        )

                    st.markdown("**Foods recorded**")

                    st.dataframe(
                        meal_entries[
                            ["food_name", "quantity_g", "meal_type"]
                        ].rename(
                            columns={
                                "food_name": "Food",
                                "quantity_g": "Quantity (g)",
                                "meal_type": "Meal"
                            }
                        ),
                        use_container_width=True,
                        hide_index=True
                    )

                    st.markdown("**Nutrients consumed in this meal**")

                    meal_nutrient_rows = []

                    for column, (display_name, unit) in (
                        available_nutrients.items()
                    ):
                        value = meal_totals.get(column)

                        meal_nutrient_rows.append({
                            "Nutrient": display_name,
                            "Amount": (
                                round(value, 2)
                                if value is not None
                                else "Unknown"
                            ),
                            "Unit": unit
                        })

                    st.dataframe(
                        pd.DataFrame(meal_nutrient_rows),
                        use_container_width=True,
                        hide_index=True
                    )

            
            # ---------------------------------------
            # FOOD DIARY WITH REMOVE OPTION
            # ---------------------------------------

            st.subheader("Your Food Diary")

            for _, entry in entries.iterrows():
                entry_id = int(entry["entry_id"])

                with st.container(border=True):
                    col1, col2 = st.columns([4, 1])

                    with col1:
                        st.markdown(f"**{entry['food_name']}**")
                        st.caption(
                            f"{entry['quantity_g']:g} g · "
                            f"{entry['meal_type']}"
                        )

                        time_value = str(entry["eaten_at"])
                        if len(time_value) >= 16:
                            st.caption(
                                f"Time eaten: {time_value[11:16]}"
                            )

                    with col2:
                        if st.button(
                            "Remove",
                            key=f"remove_entry_{entry_id}",
                            use_container_width=True
                        ):
                            st.session_state["confirm_remove_entry"] = (
                                entry_id
                            )

            # Ask for confirmation before deleting
            pending_id = st.session_state.get(
                "confirm_remove_entry"
            )

            if pending_id is not None:
                matching_entry = entries[
                    entries["entry_id"] == pending_id
                ]

                if not matching_entry.empty:
                    st.warning(
                        "Are you sure you want to remove this food entry? "
                        "Its nutrients will no longer count toward this "
                        "day's totals."
                    )

                    confirm_col, cancel_col = st.columns(2)

                    with confirm_col:
                        if st.button(
                            "Yes, remove entry",
                            key="confirm_remove_button",
                            type="primary",
                            use_container_width=True
                        ):
                            with get_connection() as connection:
                                cursor = connection.execute(
                                    """
                                    DELETE FROM food_entries
                                    WHERE entry_id = ? AND user_id = ?
                                    """,
                                    (int(pending_id), int(user_id))
                                )

                                connection.commit()

                                deleted_count = cursor.rowcount

                            del st.session_state["confirm_remove_entry"]

                            if deleted_count > 0:
                                st.success("Food entry removed successfully.")
                            else:
                                st.error("The food entry could not be found or was already removed.")

                            st.rerun()
                           
                        with get_connection() as connection:
                            connection.execute(
                                """
                                DELETE FROM food_entries
                                WHERE entry_id = ? AND user_id = ?
                                """,
                                (pending_id, user_id)
                            )

                        del st.session_state[
                            "confirm_remove_entry"
                        ]
                        st.success("Food entry removed.")
                        st.rerun()

                    with cancel_col:
                        if st.button(
                            "Cancel",
                            key="cancel_remove_button",
                            use_container_width=True
                        ):
                            del st.session_state[
                                "confirm_remove_entry"
                            ]
                            st.rerun()
                else:
                    # The selected entry is no longer in this date's list.
                    del st.session_state["confirm_remove_entry"]


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
                # END-OF-DAY REVIEW
                # ---------------------------------------
        
        st.divider()
        st.subheader("End-of-Day Review")

        st.write(
            "Review your recorded intake for the selected date "
            "and explore foods that may help you work toward "
            "your nutrition goals."
        )

        if entries.empty:
            st.info(
                "Record at least one food for the selected date "
                "to generate your review."
            )
        else:
            st.markdown("### Your intake at a glance")

            review_cols = st.columns(4)

            review_metrics = [
                ("Energy", "Energy (kcal)", "kcal"),
                ("Protein", "Protein (g)", "g"),
                ("Carbohydrates", "Carbohydrate available (g)", "g"),
                ("Fibre", "Fibre (g)", "g"),
            ]

            for index, (label, column, unit) in enumerate(review_metrics):
                with review_cols[index]:
                    value = totals.get(column)

                    st.metric(
                        label,
                        f"{value:.1f} {unit}"
                        if value is not None
                        else "Unknown"
                    )

            st.caption(
                "This review reflects foods recorded in your diary. "
                "It may not represent everything you consumed that day."
            )

            st.markdown("### Nutrients to explore")

            review_nutrients = [
                ("Protein", "Protein (g)"),
                ("Fibre", "Fibre (g)"),
                ("Iron", "Iron (mg)"),
                ("Calcium", "Calcium (mg)"),
                ("Vitamin C", "Vitamin C (mg)"),
            ]

            available_review_nutrients = [
                (label, column)
                for label, column in review_nutrients
                if column in totals
            ]

            for label, column in available_review_nutrients:
                value = totals.get(column)

                if value is None:
                    st.write(f"**{label}:** Not enough known data to total.")
                else:
                    st.write(f"**{label}:** {value:.2f} {nutrient_units[column][1]}")

            st.markdown("### Find foods for your next meal")

            st.write(
                "Choose a nutrient or nutrition goal to find food options "
                "using your existing K-Means recommendations."
            )

            review_goal = st.selectbox(
                "What would you like to focus on?",
                [
                    "Higher protein",
                    "Higher fibre",
                    "Lower energy",
                    "Specific Nutrient",
                ],
                key="end_day_review_goal",
            )

            if review_goal == "Specific Nutrient":
                review_nutrient_options = {
                    col: details[0]
                    for col, details in nutrient_units.items()
                    if col in df.columns
                }

                if review_nutrient_options:
                    review_target = st.selectbox(
                        "Choose a nutrient",
                        list(review_nutrient_options.keys()),
                        format_func=lambda col: review_nutrient_options[col],
                        key="end_day_review_nutrient",
                    )
                else:
                    review_target = None
                    st.info("No nutrient columns are available.")
            else:
                review_target = {
                    "Higher protein": "Protein (g)",
                    "Higher fibre": "Fibre (g)",
                    "Lower energy": "Energy (kcal)",
                }[review_goal]

            if review_target is not None:
                if review_target not in df.columns:
                    st.warning(
                        f"The dataset does not contain {review_target}."
                    )
                elif "KMeans_Cluster" not in df.columns:
                    st.warning("K-Means cluster labels were not found.")
                else:
                    review_data = df[
                        ["Food Name", "KMeans_Cluster", review_target]
                    ].copy()

                    review_data[review_target] = pd.to_numeric(
                        review_data[review_target],
                        errors="coerce",
                    )

                    review_data = review_data.dropna(
                        subset=["Food Name", "KMeans_Cluster", review_target]
                    )

                    if review_data.empty:
                        st.info(
                            "There are no foods with known values for "
                            "this nutrient."
                        )
                    else:
                        lower_is_better = review_goal == "Lower energy"

                        cluster_means = review_data.groupby(
                            "KMeans_Cluster"
                        )[review_target].mean()

                        best_cluster = (
                            cluster_means.idxmin()
                            if lower_is_better
                            else cluster_means.idxmax()
                        )

                        review_recommendations = review_data[
                            review_data["KMeans_Cluster"] == best_cluster
                        ].sort_values(
                            review_target,
                            ascending=lower_is_better,
                        ).head(5)

                        st.caption(
                            f"Suggested foods from K-Means cluster "
                            f"{best_cluster}; values are per 100 g."
                        )

                        st.dataframe(
                            review_recommendations.rename(
                                columns={
                                    "Food Name": "Food",
                                    "KMeans_Cluster": "Cluster",
                                    review_target: f"{review_target} per 100 g",
                                }
                            ).round(2),
                            use_container_width=True,
                            hide_index=True,
                        )

    elif page == "Nutrition Trends":
        st.markdown(
            '<p class="main-title">Nutrition Trends</p>',
            unsafe_allow_html=True
        )
        st.write(
            "Explore changes in your recorded nutrient intake over time. "
            "Only dates with food entries are included in averages; days "
            "without entries and nutrients with no known values are not treated as zero."
        )

        today = date.today()
        default_start = today - timedelta(days=27)
        selected_range = st.date_input(
            "Choose a date range (up to 28 days recommended)",
            value=(default_start, today),
            key="nutrition_trends_date_range",
        )

        if not isinstance(selected_range, (tuple, list)) or len(selected_range) != 2:
            st.info("Select both a start date and an end date to view trends.")
        elif selected_range[0] > selected_range[1]:
            st.warning("The start date must be on or before the end date.")
        else:
            start_date, end_date = selected_range
            with get_connection() as connection:
                trend_entries = pd.read_sql_query(
                    """
                    SELECT eaten_date, nutrients_json
                    FROM food_entries
                    WHERE user_id = ? AND eaten_date BETWEEN ? AND ?
                    ORDER BY eaten_date
                    """,
                    connection,
                    params=(user_id, start_date.isoformat(), end_date.isoformat()),
                )

            if trend_entries.empty:
                st.info(
                    "No food entries were found in this date range. Add meals "
                    "in Food Tracker to begin building your nutrition trends."
                )
            else:
                # Keep unlogged dates missing (NaN), not zero. For a logged day,
                # total each nutrient from its known values only; if every value
                # for a nutrient is unknown, that day's total remains missing.
                daily_records = []
                for logged_date, group in trend_entries.groupby("eaten_date", dropna=True):
                    row = {"Date": pd.to_datetime(logged_date), "Food entries": len(group)}
                    parsed_nutrients = []
                    for raw_json in group["nutrients_json"]:
                        try:
                            item = json.loads(raw_json) if raw_json else {}
                            parsed_nutrients.append(item if isinstance(item, dict) else {})
                        except (TypeError, json.JSONDecodeError):
                            parsed_nutrients.append({})

                    for nutrient in available_nutrients:
                        known_values = []
                        for nutrient_map in parsed_nutrients:
                            value = nutrient_map.get(nutrient)
                            if value is not None:
                                try:
                                    numeric_value = float(value)
                                    if pd.notna(numeric_value):
                                        known_values.append(numeric_value)
                                except (TypeError, ValueError):
                                    continue
                        row[nutrient] = sum(known_values) if known_values else float("nan")
                    daily_records.append(row)

                daily_trends = pd.DataFrame(daily_records).sort_values("Date")
                # Reindex to every calendar date so unlogged days remain visible as gaps
                # instead of making non-consecutive dates appear adjacent on the chart.
                daily_trends = daily_trends.set_index("Date").reindex(
                    pd.date_range(start=start_date, end=end_date, freq="D", name="Date")
                )
                daily_trends["Food entries"] = daily_trends["Food entries"].fillna(0).astype(int)
                daily_trends = daily_trends.reset_index()
                recorded_day_count = int((daily_trends["Food entries"] > 0).sum())
                st.caption(
                    f"Showing {start_date.strftime('%d %b %Y')} to "
                    f"{end_date.strftime('%d %b %Y')}. "
                    f"{recorded_day_count} day(s) have recorded food entries; "
                    f"{len(daily_trends) - recorded_day_count} day(s) have no entries."
                )

                st.markdown("### Time-series chart")
                st.write(
                    "View daily intake across calendar dates. The optional moving average "
                    "smooths short-term variation; gaps remain gaps when no food was logged."
                )
                chart_nutrients = [
                    col for col in [
                        "Energy (kcal)", "Protein (g)",
                        "Fibre (g)", "Carbohydrate available (g)"
                    ] if col in available_nutrients
                ]
                if chart_nutrients:
                    chosen_nutrient = st.selectbox(
                        "Choose a nutrient to chart",
                        chart_nutrients,
                        format_func=lambda col: f"{nutrient_units[col][0]} ({nutrient_units[col][1]})",
                        key="nutrition_trend_chart_nutrient",
                    )
                    show_moving_average = st.checkbox(
                        "Show 7-day moving average",
                        value=True,
                        key="nutrition_trend_show_moving_average",
                    )
                    chart_data = daily_trends.set_index("Date")[[chosen_nutrient]].copy()
                    chart_data = chart_data.rename(columns={chosen_nutrient: "Daily recorded total"})
                    if show_moving_average:
                        # This is a calendar-day rolling window because all dates are present.
                        chart_data["7-day moving average"] = (
                            daily_trends.set_index("Date")[chosen_nutrient]
                            .rolling(window=7, min_periods=3)
                            .mean()
                        )
                    st.line_chart(chart_data)
                    st.caption(
                        "The 7-day moving average appears after at least 3 days with known values "
                        "within a 7-calendar-day window. Missing dates are not treated as zero."
                    )
                else:
                    st.info("The dataset does not contain the usual energy, protein, fibre, or carbohydrate columns.")

                st.markdown("### Daily totals")
                daily_display = daily_trends.copy()
                display_columns = [
                    col for col in [
                        "Energy (kcal)", "Protein (g)", "Fat (g)",
                        "Carbohydrate available (g)", "Fibre (g)"
                    ] if col in daily_display.columns
                ]
                rename_map = {col: f"{nutrient_units[col][0]} ({nutrient_units[col][1]})" for col in display_columns}
                daily_display = daily_display[["Date", "Food entries"] + display_columns].rename(columns=rename_map)
                daily_display["Date"] = daily_display["Date"].dt.strftime("%d %b %Y")
                st.dataframe(daily_display.round(2), use_container_width=True, hide_index=True)

                st.markdown("### Weekly averages")
                weekly_source = daily_trends.copy()
                weekly_source["Week starting"] = (
                    weekly_source["Date"] - pd.to_timedelta(weekly_source["Date"].dt.weekday, unit="D")
                ).dt.normalize()
                weekly_nutrients = [
                    col for col in [
                        "Energy (kcal)", "Protein (g)", "Fibre (g)",
                        "Carbohydrate available (g)"
                    ] if col in weekly_source.columns
                ]
                if weekly_nutrients:
                    weekly_rows = []
                    for week_start, week_group in weekly_source.groupby("Week starting", sort=True):
                        for nutrient in weekly_nutrients:
                            known_daily = week_group[nutrient].dropna()
                            weekly_rows.append({
                                "Week starting": week_start.strftime("%d %b %Y"),
                                "Nutrient": f"{nutrient_units[nutrient][0]} ({nutrient_units[nutrient][1]})",
                                "Average per recorded day": round(known_daily.mean(), 2) if not known_daily.empty else "Unknown",
                                "Days with known values": int(known_daily.count()),
                            })
                    st.dataframe(pd.DataFrame(weekly_rows), use_container_width=True, hide_index=True)
                    st.caption(
                        "Weekly averages are calculated from days with a known daily total for each nutrient, "
                        "not from unlogged days."
                    )

                # Direction of change across the selected date range, based only on known daily totals.
                st.markdown("### Daily intake direction")
                direction_nutrients = [
                    col for col in [
                        "Energy (kcal)", "Protein (g)", "Fibre (g)",
                        "Carbohydrate available (g)"
                    ] if col in daily_trends.columns
                ]
                direction_rows = []
                for nutrient in direction_nutrients:
                    known = daily_trends[["Date", nutrient]].dropna().sort_values("Date")
                    if len(known) < 2:
                        direction_rows.append({
                            "Nutrient": f"{nutrient_units[nutrient][0]} ({nutrient_units[nutrient][1]})",
                            "First recorded day": "Not enough data",
                            "Latest recorded day": "Not enough data",
                            "Change": "Not enough data",
                            "Direction": "Need at least 2 recorded days",
                        })
                        continue
                    first_value = float(known.iloc[0][nutrient])
                    latest_value = float(known.iloc[-1][nutrient])
                    difference = latest_value - first_value
                    tolerance = max(abs(first_value) * 0.05, 0.01)
                    if difference > tolerance:
                        direction = "Increasing"
                    elif difference < -tolerance:
                        direction = "Decreasing"
                    else:
                        direction = "Roughly stable"
                    direction_rows.append({
                        "Nutrient": f"{nutrient_units[nutrient][0]} ({nutrient_units[nutrient][1]})",
                        "First recorded day": round(first_value, 2),
                        "Latest recorded day": round(latest_value, 2),
                        "Change": round(difference, 2),
                        "Direction": direction,
                    })
                if direction_rows:
                    st.dataframe(pd.DataFrame(direction_rows), use_container_width=True, hide_index=True)
                    st.caption("Direction compares the first and latest days with known values in the selected range; it is descriptive, not a forecast.")

                # Compare the two most recent calendar weeks represented in the selected range.
                st.markdown("### Week-to-week comparison")
                comparison_nutrients = [
                    col for col in [
                        "Energy (kcal)", "Protein (g)", "Fibre (g)",
                        "Carbohydrate available (g)"
                    ] if col in daily_trends.columns
                ]
                comparison_source = daily_trends.copy()
                comparison_source["Week starting"] = (
                    comparison_source["Date"] - pd.to_timedelta(comparison_source["Date"].dt.weekday, unit="D")
                ).dt.normalize()
                represented_weeks = sorted(
                    comparison_source.loc[comparison_source["Food entries"] > 0, "Week starting"]
                    .dropna().unique()
                )
                if len(represented_weeks) < 2:
                    st.info("Record food on dates in at least two different calendar weeks to compare weekly averages.")
                else:
                    previous_week, latest_week = represented_weeks[-2], represented_weeks[-1]
                    previous_group = comparison_source[comparison_source["Week starting"] == previous_week]
                    latest_group = comparison_source[comparison_source["Week starting"] == latest_week]
                    comparison_rows = []
                    insight_lines = []
                    for nutrient in comparison_nutrients:
                        previous_known = previous_group[nutrient].dropna()
                        latest_known = latest_group[nutrient].dropna()
                        previous_avg = previous_known.mean() if not previous_known.empty else None
                        latest_avg = latest_known.mean() if not latest_known.empty else None
                        label = f"{nutrient_units[nutrient][0]} ({nutrient_units[nutrient][1]})"
                        if previous_avg is None or latest_avg is None:
                            comparison_rows.append({
                                "Nutrient": label,
                                "Previous week average": round(previous_avg, 2) if previous_avg is not None else "Unknown",
                                "Latest week average": round(latest_avg, 2) if latest_avg is not None else "Unknown",
                                "Difference": "Not enough known values",
                                "Recorded days (previous/latest)": f"{len(previous_known)}/{len(latest_known)}",
                            })
                            continue
                        difference = latest_avg - previous_avg
                        tolerance = max(abs(previous_avg) * 0.05, 0.01)
                        if difference > tolerance:
                            change_word = "higher"
                        elif difference < -tolerance:
                            change_word = "lower"
                        else:
                            change_word = "about the same"
                        comparison_rows.append({
                            "Nutrient": label,
                            "Previous week average": round(previous_avg, 2),
                            "Latest week average": round(latest_avg, 2),
                            "Difference": round(difference, 2),
                            "Recorded days (previous/latest)": f"{len(previous_known)}/{len(latest_known)}",
                        })
                        insight_lines.append(
                            f"Your recorded {nutrient_units[nutrient][0].lower()} intake was {change_word} "
                            f"in the latest week ({latest_avg:.2f} {nutrient_units[nutrient][1]}) "
                            f"than the previous week ({previous_avg:.2f} {nutrient_units[nutrient][1]})."
                            if change_word != "about the same" else
                            f"Your recorded {nutrient_units[nutrient][0].lower()} intake was about the same "
                            f"in both weeks ({latest_avg:.2f} {nutrient_units[nutrient][1]} in the latest week)."
                        )
                    st.caption(
                        f"Comparing weeks starting {pd.Timestamp(previous_week).strftime('%d %b %Y')} and "
                        f"{pd.Timestamp(latest_week).strftime('%d %b %Y')}."
                    )
                    st.dataframe(pd.DataFrame(comparison_rows), use_container_width=True, hide_index=True)
                    st.markdown("### Personalised habit insights")
                    if insight_lines:
                        for insight in insight_lines:
                            st.write(f"- {insight}")
                    else:
                        st.info("There are not enough known nutrient totals in both weeks to generate insights yet.")
                    st.caption("Insights describe your logged records only. They do not assume that unlogged days mean zero intake or provide medical advice.")

                st.markdown("### Recurring weekday patterns")
                weekday_nutrient = st.selectbox(
                    "Choose a nutrient for weekday patterns",
                    [col for col in available_nutrients if col in daily_trends.columns],
                    format_func=lambda col: f"{nutrient_units[col][0]} ({nutrient_units[col][1]})",
                    key="nutrition_trend_weekday_nutrient",
                )
                weekday_data = daily_trends.dropna(subset=[weekday_nutrient]).copy()
                if weekday_data.empty:
                    st.info("There are no known values for this nutrient in the selected period.")
                else:
                    weekday_data["Weekday"] = weekday_data["Date"].dt.day_name()
                    weekday_order = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
                    weekday_summary = (
                        weekday_data.groupby("Weekday")[weekday_nutrient]
                        .agg([("Average", "mean"), ("Recorded days", "count")])
                        .reindex(weekday_order)
                        .dropna(subset=["Average"])
                        .reset_index()
                    )
                    weekday_summary["Average"] = weekday_summary["Average"].round(2)
                    weekday_summary = weekday_summary.rename(columns={
                        "Weekday": "Day of week",
                        "Average": f"Average {nutrient_units[weekday_nutrient][0]} ({nutrient_units[weekday_nutrient][1]})"
                    })
                    st.bar_chart(weekday_summary.set_index("Day of week").iloc[:, 0])
                    st.dataframe(weekday_summary, use_container_width=True, hide_index=True)
                    st.caption(
                        "Weekday patterns are descriptive and become more useful as you record more weeks. "
                        "They reflect recorded food entries, not necessarily your complete intake."
                    )

    elif page == "Nutrition Targets":
        st.markdown('<p class="main-title">Daily Nutrition Targets</p>', unsafe_allow_html=True)
        st.write(
            "Set daily targets to compare with the foods you record. You can use "
            "a profile-based estimate for energy and protein, or enter your own targets."
        )
        with get_connection() as connection:
            profile = connection.execute(
                "SELECT age, sex, height_cm, weight_kg, activity_level FROM users WHERE user_id = ?",
                (user_id,),
            ).fetchone()
            saved_targets = connection.execute(
                "SELECT nutrient, target_value, target_mode FROM user_nutrition_targets WHERE user_id = ?",
                (user_id,),
            ).fetchall()
        saved = {row['nutrient']: row for row in saved_targets}
        automatic_targets = estimate_daily_targets(profile)
        mode = st.radio(
            "How would you like to set targets?",
            ["Automatic estimate from my profile", "Enter targets manually"],
            key="nutrition_target_mode",
        )
        if mode == "Automatic estimate from my profile":
            st.caption(
                "Automatic estimates are available when age, sex, height, weight, and activity level are provided. "
                "Energy uses the Mifflin–St Jeor equation with an activity factor; protein uses 0.8 g/kg/day. "
                "These are estimates, not medical prescriptions. Micronutrient targets can be set manually below."
            )
            if automatic_targets:
                st.write("Estimated targets")
                for nutrient, value in automatic_targets.items():
                    st.metric(f"{nutrient_units.get(nutrient, (nutrient, ''))[0]} per day", f"{value} {nutrient_units.get(nutrient, ('', ''))[1]}")
            else:
                st.warning("Your profile is missing details needed for an estimate. Add age, sex, height, weight, and activity level, or choose manual targets.")
        st.markdown("### Set or update targets")
        targetable = [col for col in available_nutrients if col not in ("Energy (kJ)",)]
        with st.form("nutrition_targets_form"):
            new_targets = {}
            for nutrient in targetable:
                label, unit = nutrient_units[nutrient]
                default = None
                if mode == "Automatic estimate from my profile" and nutrient in automatic_targets:
                    default = float(automatic_targets[nutrient])
                elif nutrient in saved:
                    default = float(saved[nutrient]['target_value'])
                # Streamlit number_input needs a numeric default; 0 means leave unset.
                val = st.number_input(
                    f"{label} target ({unit}/day)", min_value=0.0,
                    value=float(default or 0.0), step=1.0 if unit in ('kcal', 'mg', 'mcg') else 0.5,
                    key=f"target_input_{nutrient}",
                    help="Enter 0 to leave this target unset. Use a reference from your clinician or a trusted nutrition guideline where appropriate."
                )
                new_targets[nutrient] = val
            submitted_targets = st.form_submit_button("Save daily targets", use_container_width=True)
        if submitted_targets:
            with get_connection() as connection:
                for nutrient, value in new_targets.items():
                    if value > 0:
                        target_mode = "Automatic" if mode == "Automatic estimate from my profile" and nutrient in automatic_targets else "Manual"
                        connection.execute(
                            """INSERT INTO user_nutrition_targets (user_id, nutrient, target_value, target_mode, updated_at)
                               VALUES (?, ?, ?, ?, ?)
                               ON CONFLICT(user_id, nutrient) DO UPDATE SET
                                 target_value=excluded.target_value,
                                 target_mode=excluded.target_mode,
                                 updated_at=excluded.updated_at""",
                            (user_id, nutrient, float(value), target_mode, datetime.now().isoformat(timespec="seconds")),
                        )
                    else:
                        connection.execute(
                            "DELETE FROM user_nutrition_targets WHERE user_id = ? AND nutrient = ?",
                            (user_id, nutrient),
                        )
            st.success("Your daily targets have been saved for this account.")
            st.rerun()
        if saved:
            st.markdown("### Currently saved targets")
            st.dataframe(pd.DataFrame([
                {"Nutrient": nutrient_units.get(row['nutrient'], (row['nutrient'], ''))[0],
                 "Daily target": row['target_value'],
                 "Unit": nutrient_units.get(row['nutrient'], ('', ''))[1],
                 "Source": row['target_mode']}
                for row in saved.values()
            ]), use_container_width=True, hide_index=True)

    elif page == "Health Profile":
        st.markdown('<p class="main-title">Health & Nutrition Profile</p>', unsafe_allow_html=True)
        st.write("Choose optional health-related nutrition preferences. These settings personalize educational food suggestions; they do not diagnose or treat medical conditions.")
        with get_connection() as connection:
            saved_pref = connection.execute(
                "SELECT conditions_json, menstrual_nutrition FROM user_health_preferences WHERE user_id = ?",
                (user_id,),
            ).fetchone()
        saved_conditions = []
        menstrual_default = "No"
        if saved_pref:
            try:
                saved_conditions = json.loads(saved_pref["conditions_json"] or "[]")
            except (TypeError, json.JSONDecodeError):
                saved_conditions = []
            menstrual_default = saved_pref["menstrual_nutrition"] or "No"
        condition_options = ["Diabetes", "Hypertension", "High cholesterol", "Iron deficiency"]
        selected_conditions = st.multiselect(
            "Select any relevant health conditions", condition_options,
            default=([c for c in saved_conditions if c in condition_options] if saved_pref else ["Diabetes"]),
            help="You may select more than one, or leave this blank. Only select conditions that have been diagnosed by a healthcare professional."
        )
        menstrual_choice = st.radio(
            "Would you like menstrual nutrition recommendations?",
            ["Yes", "No", "Prefer not to say"],
            index=["Yes", "No", "Prefer not to say"].index(menstrual_default) if saved_pref and menstrual_default in ["Yes", "No", "Prefer not to say"] else 0,
            horizontal=True,
        )
        if st.button("Save health preferences", type="primary"):
            with get_connection() as connection:
                connection.execute(
                    """INSERT INTO user_health_preferences (user_id, conditions_json, menstrual_nutrition, updated_at)
                       VALUES (?, ?, ?, ?)
                       ON CONFLICT(user_id) DO UPDATE SET
                       conditions_json=excluded.conditions_json,
                       menstrual_nutrition=excluded.menstrual_nutrition,
                       updated_at=excluded.updated_at""",
                    (user_id, json.dumps(selected_conditions), menstrual_choice, datetime.now().isoformat(timespec="seconds")),
                )
            st.success("Your health and nutrition preferences have been saved.")
            st.rerun()
        st.caption("You can change or clear these preferences at any time. NutriTrack does not use this information to make a diagnosis or recommend medication changes.")

    elif page == "Food Recommendations":

        # Automatic recommendations combine recent food logs, saved targets,
        # health preferences, nutrient composition, and existing K-Means labels.
        st.markdown("### Your automatic recommendations")
        st.write(
            "These suggestions update from your recent food diary and saved health profile. "
            "They are educational food ideas, not disease treatment or a prescribed meal plan."
        )

        auto_end = date.today()
        auto_start = auto_end - timedelta(days=13)
        with get_connection() as connection:
            auto_logs = pd.read_sql_query(
                """
                SELECT eaten_date, food_name, quantity_g, meal_type, nutrients_json
                FROM food_entries
                WHERE user_id = ? AND eaten_date BETWEEN ? AND ?
                ORDER BY eaten_date DESC
                """,
                connection,
                params=(user_id, auto_start.isoformat(), auto_end.isoformat()),
            )
            auto_target_rows = connection.execute(
                "SELECT nutrient, target_value FROM user_nutrition_targets WHERE user_id = ?",
                (user_id,),
            ).fetchall()
            auto_pref = connection.execute(
                "SELECT conditions_json, menstrual_nutrition FROM user_health_preferences WHERE user_id = ?",
                (user_id,),
            ).fetchone()

        auto_targets = {
            row["nutrient"]: float(row["target_value"])
            for row in auto_target_rows if row["target_value"] is not None
        }
        auto_conditions = []
        auto_menstrual = False
        if auto_pref:
            try:
                auto_conditions = json.loads(auto_pref["conditions_json"] or "[]")
            except (TypeError, json.JSONDecodeError):
                auto_conditions = []
            auto_menstrual = auto_pref["menstrual_nutrition"] == "Yes"

        # Average logged daily totals over days with entries, not over unlogged days.
        auto_daily = []
        if not auto_logs.empty:
            for log_day, day_group in auto_logs.groupby("eaten_date"):
                day_totals = {}
                for nutrient in available_nutrients:
                    vals = []
                    for raw in day_group["nutrients_json"]:
                        try:
                            item = json.loads(raw) if raw else {}
                            val = item.get(nutrient) if isinstance(item, dict) else None
                            if val is not None and pd.notna(float(val)):
                                vals.append(float(val))
                        except (TypeError, ValueError, json.JSONDecodeError):
                            continue
                    if vals:
                        day_totals[nutrient] = sum(vals)
                auto_daily.append(day_totals)

        auto_avg = {}
        if auto_daily:
            for nutrient in available_nutrients:
                vals = [d[nutrient] for d in auto_daily if nutrient in d]
                if vals:
                    auto_avg[nutrient] = sum(vals) / len(vals)

        # Priorities are food-composition signals only. Do not infer saturated fat
        # from total fat or treat one day's log as evidence of a deficiency.
        health_priorities = {
            "Diabetes": [("Fibre (g)", 1.0), ("Carbohydrate available (g)", -0.35)],
            "Hypertension": [("Sodium (mg)", -1.0), ("Potassium (mg)", 0.5)],
            "High cholesterol": [("Fibre (g)", 1.0)],
            "Iron deficiency": [("Iron (mg)", 1.0), ("Vitamin C (mg)", 0.5)],
        }
        automatic_weights = {}
        for condition in auto_conditions:
            for nutrient, weight in health_priorities.get(condition, []):
                automatic_weights[nutrient] = automatic_weights.get(nutrient, 0) + weight
        if auto_menstrual:
            for nutrient, weight in [
                ("Iron (mg)", 0.8), ("Vitamin C (mg)", 0.5),
                ("Calcium (mg)", 0.35), ("Magnesium (mg)", 0.35)
            ]:
                automatic_weights[nutrient] = automatic_weights.get(nutrient, 0) + weight

        # Add user-specific gaps from targets and recent logged averages.
        for nutrient, target in auto_targets.items():
            if nutrient in df.columns and target > 0 and nutrient in auto_avg:
                gap_fraction = max(0.0, min(1.0, (target - auto_avg[nutrient]) / target))
                if gap_fraction > 0:
                    automatic_weights[nutrient] = automatic_weights.get(nutrient, 0) + gap_fraction

        automatic_weights = {
            nutrient: weight for nutrient, weight in automatic_weights.items()
            if nutrient in df.columns and weight != 0
        }

        if auto_logs.empty:
            st.info(
                f"No food entries were found in the last 14 days ({auto_start:%d %b}–{auto_end:%d %b}). "
                "Log meals in Food Tracker to activate recommendations based on your actual intake."
            )
        elif not automatic_weights:
            st.info(
                "Your recent food logs are available, but no relevant saved targets or health-profile "
                "priorities are available yet. Add daily targets or update Health Profile to personalize suggestions."
            )
        else:
            st.caption(
                f"Analyzed {auto_logs['eaten_date'].nunique()} logged day(s) from the last 14 days. "
                "Unlogged days are excluded from averages."
            )
            if auto_avg:
                trend_gap_rows = []
                for nutrient, target in auto_targets.items():
                    if nutrient in auto_avg and target > 0:
                        trend_gap_rows.append({
                            "Nutrient": nutrient_units.get(nutrient, (nutrient, ""))[0],
                            "Recent daily average": round(auto_avg[nutrient], 2),
                            "Target": round(target, 2),
                            "Average progress (%)": round(auto_avg[nutrient] / target * 100, 1),
                        })
                if trend_gap_rows:
                    st.markdown("**Recent intake compared with your targets**")
                    st.dataframe(
                        pd.DataFrame(trend_gap_rows).sort_values("Average progress (%)"),
                        use_container_width=True, hide_index=True
                    )

           # Exclude seasonings and other items that are not usually recommended as main foods
            excluded_sections = [
                "Condiments and Spices",
                "Oils and Fat",
                "Sugar and Swetened Products",
                "Beverages"
            ]

            eligible_foods = df[
                ~df["Section"].astype(str).str.strip().isin(excluded_sections)
            ].copy()

            candidate_foods = eligible_foods[
                ["Food Name", "Section", "KMeans_Cluster"]
            ].copy()

            candidate_foods = candidate_foods.dropna(
                subset=["Food Name", "KMeans_Cluster"]
            )

            candidate_foods = candidate_foods.drop_duplicates(
                subset=["Food Name"]
            ).copy() 

            # Percentile ranks put different nutrient units on a comparable scale.
            score = pd.Series(0.0, index=candidate_foods.index)
            score_weight = 0.0
            for nutrient, weight in automatic_weights.items():
                values = pd.to_numeric(df.loc[candidate_foods.index, nutrient], errors="coerce")
                if values.notna().sum() < 2:
                    continue
                percentile = values.rank(pct=True)
                if weight < 0:
                    percentile = 1 - percentile
                score = score.add(percentile.fillna(0) * abs(weight), fill_value=0)
                score_weight += abs(weight)

            if score_weight == 0:
                st.info("The dataset does not have enough usable nutrient values for these priorities.")
            else:
                candidate_foods["Recommendation score"] = score / score_weight
                ranked_foods = candidate_foods.sort_values(
                    "Recommendation score", ascending=False
                ).head(12).copy()

                # Avoid recommending foods the user has already logged repeatedly
                # as the only suggestions; retain them but label the distinction.
                recent_counts = auto_logs["food_name"].astype(str).str.casefold().value_counts()
                ranked_foods["Recently logged"] = ranked_foods["Food Name"].astype(str).str.casefold().map(
                    lambda name: "Yes" if recent_counts.get(name, 0) else "No"
                )
                display_nutrients = [
                    n for n in automatic_weights if n in df.columns
                ]
                st.markdown("#### Foods to consider adding")
                food_display = ranked_foods[
                    [
                        "Food Name",
                        "Section",
                        "KMeans_Cluster",
                        "Recommendation score",
                        "Recently logged"
                    ]
                ].copy()
                for nutrient in display_nutrients[:4]:
                    food_display[nutrient] = pd.to_numeric(
                        df.loc[ranked_foods.index, nutrient], errors="coerce"
                    ).round(2)
                st.dataframe(food_display, use_container_width=True, hide_index=True)
                st.caption(
                    "Foods are ranked by relative nutrient composition per 100 g and selected across "
                    "your dataset's existing K-Means groups. This is not a clinical suitability score."
                )

                st.markdown("#### Simple meal combinations")
                st.write(
                    "These are food-combination ideas assembled from highly ranked dataset foods, "
                    "not tested recipes or fixed portion prescriptions."
                )
                meal_candidates = ranked_foods["Food Name"].astype(str).tolist()
                if len(meal_candidates) >= 3:
                    st.markdown(
                        f"- **Breakfast idea:** {meal_candidates[0]} with {meal_candidates[1]}."
                    )
                    st.markdown(
                        f"- **Lunch idea:** {meal_candidates[2]} with {meal_candidates[3] if len(meal_candidates) > 3 else meal_candidates[0]}."
                    )
                    st.markdown(
                        f"- **Dinner idea:** {meal_candidates[4] if len(meal_candidates) > 4 else meal_candidates[1]} "
                        f"with {meal_candidates[5] if len(meal_candidates) > 5 else meal_candidates[2]}."
                    )
                    if len(meal_candidates) > 6:
                        st.markdown(
                            f"- **Snack idea:** {meal_candidates[6]}."
                        )
                else:
                    st.info("More foods with usable nutrient values are needed to assemble meal ideas.")

                st.caption(
                    "For diabetes, recommendations consider fibre and carbohydrate awareness; "
                    "they do not calculate blood-glucose responses. For high cholesterol, the dataset "
                    "does not provide a verified saturated-fat measure in this scoring rule. "
                    "Discuss disease-specific dietary changes with your healthcare professional."
                )

        st.markdown(
            '<p class="main-title">Food Recommendations</p>',
            unsafe_allow_html=True
        )
        st.write(
            "Choose a nutrition goal. NutriTrack compares foods using their "
            "existing K-Means cluster labels and nutrient values per 100 g."
        )
        with get_connection() as connection:
            pref_row = connection.execute(
                "SELECT conditions_json, menstrual_nutrition FROM user_health_preferences WHERE user_id = ?",
                (user_id,),
            ).fetchone()
        active_conditions = []
        menstrual_enabled = False
        if pref_row:
            try:
                active_conditions = json.loads(pref_row["conditions_json"] or "[]")
            except (TypeError, json.JSONDecodeError):
                active_conditions = []
            menstrual_enabled = pref_row["menstrual_nutrition"] == "Yes"
        st.markdown("### Health-aware food suggestions")
        if not active_conditions and not menstrual_enabled:
            st.info("You have not selected any health preferences yet. You can set them on the Health Profile page; general recommendations remain available.")
        else:
            st.caption("Active profile: " + (", ".join(active_conditions) if active_conditions else "No selected condition") + (" · Menstrual nutrition enabled" if menstrual_enabled else ""))
            # Nutrient priorities are food-selection aids, not clinical prescriptions.
            priority_rules = {
                "Diabetes": [("Fibre (g)", True), ("Carbohydrate available (g)", False)],
                "Hypertension": [("Sodium (mg)", False), ("Potassium (mg)", True)],
                "High cholesterol": [("Fibre (g)", True), ("Fat (g)", False)],
                "Iron deficiency": [("Iron (mg)", True), ("Vitamin C (mg)", True)],
            }
            selected_health_rule = st.selectbox(
                "Choose a health focus", active_conditions + (["Menstrual nutrition"] if menstrual_enabled else []),
                key="health_focus_recommendation"
            )
            if selected_health_rule == "Menstrual nutrition":
                priorities = [("Iron (mg)", True), ("Vitamin C (mg)", True), ("Calcium (mg)", True), ("Magnesium (mg)", True)]
                st.write("Suggestions emphasize dietary sources of iron and supporting nutrients. Food alone may not correct iron deficiency or treat menstrual symptoms.")
            else:
                priorities = priority_rules.get(selected_health_rule, [])
                st.write("Suggestions use the nutrient priorities below as general food-composition guidance. They are not a prescribed disease diet.")
            available_priorities = [(col, high) for col, high in priorities if col in df.columns]
            if available_priorities:
                focus_nutrient, prefer_high = st.selectbox(
                    "Nutrient to prioritize", available_priorities,
                    format_func=lambda item: f"{nutrient_units.get(item[0], (item[0], ''))[0]} ({'higher' if item[1] else 'lower'} per 100 g)",
                    key="health_focus_nutrient"
                )
                health_foods = df[["Food Name", "Food Type", "KMeans_Cluster", focus_nutrient]].copy()
                health_foods[focus_nutrient] = pd.to_numeric(health_foods[focus_nutrient], errors="coerce")
                health_foods = health_foods.dropna(subset=["Food Name", "KMeans_Cluster", focus_nutrient])
                if not health_foods.empty:
                    cluster_avg = health_foods.groupby("KMeans_Cluster")[focus_nutrient].mean()
                    chosen_cluster = cluster_avg.idxmax() if prefer_high else cluster_avg.idxmin()
                    health_suggestions = health_foods[health_foods["KMeans_Cluster"] == chosen_cluster].sort_values(focus_nutrient, ascending=not prefer_high).head(8)
                    st.caption(f"Selected from K-Means cluster {chosen_cluster}; nutrient values are per 100 g. Portion size and the rest of the meal still matter.")
                    st.dataframe(health_suggestions.rename(columns={"Food Name":"Food", "Food Type":"Category", "KMeans_Cluster":"Cluster", focus_nutrient:f"{focus_nutrient} per 100 g"}).round(2), use_container_width=True, hide_index=True)
                else:
                    st.info("No matching food nutrient values are available in the dataset.")
            else:
                st.info("The dataset does not contain the nutrient columns needed for this health focus.")
            st.warning("For diabetes, hypertension, high cholesterol or diagnosed iron deficiency, use these as educational suggestions only. Individual needs vary; consult a qualified healthcare professional, especially if taking medication, pregnant, or experiencing heavy menstrual bleeding.")


        st.markdown("### Today's intake versus your targets")
        with get_connection() as connection:
            target_rows = connection.execute(
                "SELECT nutrient, target_value FROM user_nutrition_targets WHERE user_id = ?",
                (user_id,),
            ).fetchall()
            today_entries = pd.read_sql_query(
                "SELECT nutrients_json FROM food_entries WHERE user_id = ? AND eaten_date = ?",
                connection, params=(user_id, date.today().isoformat())
            )
        targets = {row['nutrient']: float(row['target_value']) for row in target_rows}
        today_totals = {}
        if not today_entries.empty:
            for nutrient in targets:
                values = []
                for raw in today_entries['nutrients_json']:
                    try:
                        item = json.loads(raw) if raw else {}
                        if item.get(nutrient) is not None:
                            values.append(float(item[nutrient]))
                    except (TypeError, ValueError, json.JSONDecodeError):
                        continue
                today_totals[nutrient] = sum(values) if values else 0.0
        if not targets:
            st.info("Set your daily targets on the Nutrition Targets page to see personalized nutrient gaps here.")
        else:
            gap_rows = []
            for nutrient, target_value in targets.items():
                consumed = today_totals.get(nutrient, 0.0)
                remaining = max(0.0, target_value - consumed)
                gap_rows.append({
                    "Nutrient": nutrient_units.get(nutrient, (nutrient, ""))[0],
                    "Consumed": round(consumed, 2),
                    "Daily target": round(target_value, 2),
                    "Remaining to target": round(remaining, 2),
                    "Progress (%)": round(min(100.0, consumed / target_value * 100), 1) if target_value > 0 else 0,
                })
            gap_df = pd.DataFrame(gap_rows).sort_values("Progress (%)")
            st.dataframe(gap_df, use_container_width=True, hide_index=True)
            gaps = [row for row in gap_rows if row["Remaining to target"] > 0]
            if gaps:
                lowest = gaps[0]
                st.caption(
                    f"Largest current gap by percentage progress: {lowest['Nutrient']}. "
                    "This is a food-log estimate, not a diagnosis; incomplete logging can make gaps appear larger."
                )

        recommendation_goal = st.selectbox(
            "Choose a nutrition goal",
            [
                "Address a nutrient gap",
                "Higher protein",
                "Higher fibre",
                "Lower energy",
                "Specific Nutrient",
            ],
            key="standalone_recommendation_goal",
        )

        if recommendation_goal == "Address a nutrient gap":
            if targets:
                gap_nutrients = [n for n in targets if n in df.columns and today_totals.get(n, 0.0) < targets[n]]
                if gap_nutrients:
                    recommendation_target = st.selectbox(
                        "Choose a nutrient gap to address",
                        gap_nutrients,
                        format_func=lambda col: nutrient_units.get(col, (col, ""))[0],
                        key="gap_recommendation_nutrient",
                    )
                else:
                    recommendation_target = None
                    st.success("No logged target gaps today, based on your current entries and saved targets.")
            else:
                recommendation_target = None
                st.info("Save daily targets on the Nutrition Targets page before choosing gap-based recommendations.")
        elif recommendation_goal == "Specific Nutrient":
            recommendation_nutrient_options = {
                col: details[0]
                for col, details in nutrient_units.items()
                if col in df.columns
            }
            if recommendation_nutrient_options:
                recommendation_target = st.selectbox(
                    "Choose a nutrient",
                    list(recommendation_nutrient_options.keys()),
                    format_func=lambda col: recommendation_nutrient_options[col],
                    key="standalone_recommendation_nutrient",
                )
            else:
                recommendation_target = None
                st.info("No nutrient columns are available for recommendations.")
        else:
            recommendation_target = {
                "Higher protein": "Protein (g)",
                "Higher fibre": "Fibre (g)",
                "Lower energy": (
                    "Energy (kcal)" if "Energy (kcal)" in df.columns
                    else "Energy (kJ)"
                ),
            }[recommendation_goal]

        recommendation_food_type = st.selectbox(
            "Filter food category",
            ["All foods", "Single-ingredient foods", "Mixed Dishes"],
            key="recommendation_food_type",
        )

        if recommendation_target is not None:
            if recommendation_target not in df.columns:
                st.warning(
                    f"The dataset does not contain {recommendation_target}."
                )
            elif "KMeans_Cluster" not in df.columns:
                st.warning("K-Means cluster labels were not found in the dataset.")
            else:
                recommendation_data = df[
                    [
                        "Food Name",
                        "Section",
                        "Food Type",
                        "KMeans_Cluster",
                        recommendation_target
                    ]
                ].copy()
                # Exclude seasonings and non-meal categories
                excluded_sections = [
                    "Condiments and Spices",
                    "Oils and Fat",
                    "Sugar and Swetened Products",
                    "Beverages"
                ]

                recommendation_data = recommendation_data[
                    ~recommendation_data["Section"].astype(str).str.strip().isin(
                        excluded_sections
                    )
                ].copy()

                recommendation_data[recommendation_target] = pd.to_numeric(
                    recommendation_data[recommendation_target],
                    errors="coerce",
                )
                recommendation_data = recommendation_data.dropna(
                    subset=["Food Name", "KMeans_Cluster", recommendation_target]
                )

                if recommendation_food_type != "All foods":
                    recommendation_data = recommendation_data[
                        recommendation_data["Food Type"] == recommendation_food_type
                    ]

                if recommendation_data.empty:
                    st.info("No foods with known values match these selections.")
                else:
                    lower_is_better = recommendation_goal == "Lower energy"
                    cluster_means = recommendation_data.groupby(
                        "KMeans_Cluster"
                    )[recommendation_target].mean()

                    best_cluster = (
                        cluster_means.idxmin()
                        if lower_is_better
                        else cluster_means.idxmax()
                    )

                    recommendations = recommendation_data[
                        recommendation_data["KMeans_Cluster"] == best_cluster
                    ].sort_values(
                        recommendation_target,
                        ascending=lower_is_better,
                    ).head(10)

                    st.caption(
                        f"Foods are selected from K-Means cluster {best_cluster}. "
                        "Nutrient values are per 100 g; choose foods that fit "
                        "your overall dietary needs."
                    )
                    st.dataframe(
                        recommendations[
                            ["Food Name", "Food Type", "KMeans_Cluster", recommendation_target]
                        ].rename(
                            columns={
                                "Food Name": "Food",
                                "Food Type": "Category",
                                "KMeans_Cluster": "Cluster",
                                recommendation_target: f"{recommendation_target} per 100 g",
                            }
                        ).round(2),
                        use_container_width=True,
                        hide_index=True,
                    )

    elif page == "About the App":
        st.markdown(
            '<p class="main-title">About NutriTrack</p>',
            unsafe_allow_html=True
        )
        st.write(
            "NutriTrack is a personal nutrition tracker built around a food "
            "composition dataset. It lets signed-in users record foods, "
            "quantities, meal types, dates, and eating times, then review "
            "known nutrient totals."
        )
        st.write(
            "Food recommendations use the K-Means cluster labels already "
            "stored in the dataset. Nutrient values are shown per 100 g "
            "unless a section specifically reports the quantity recorded "
            "in a food diary."
        )
        st.caption(
            "Nutrition data can contain unknown values. Displayed totals may "
            "therefore be incomplete and should not be treated as medical advice."
        )