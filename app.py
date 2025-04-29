import random
import requests
import streamlit as st
import pandas as pd
import altair as alt
from typing import List, Dict, Tuple

# ------------------------
# 🔐 Spoonacular API Key
# ------------------------
API_KEY = "37b9d6cf14e549739544c7a1eb1ca971"
PRICE_CURRENCY = "CHF"  # Wir behandeln Spoonacular‑USD ≈ CHF (vereinfachend)

# ------------------------
# 🔍 Spoonacular Search
# ------------------------

def search_recipes_by_protein(
    min_protein: int = 25, max_calories: int | None = None, number: int = 5
) -> List[Dict]:
    """Query Spoonacular for high‑protein recipes and return nutrition & price."""
    search_url = "https://api.spoonacular.com/recipes/complexSearch"
    params = {
        "apiKey": API_KEY,
        "minProtein": min_protein,
        "number": number,
        "addRecipeInformation": False,
    }
    if max_calories:
        params["maxCalories"] = max_calories

    response = requests.get(search_url, params=params).json()
    results = []
    for recipe in response.get("results", []):
        r_id = recipe["id"]
        details = requests.get(
            f"https://api.spoonacular.com/recipes/{r_id}/information",
            params={"apiKey": API_KEY, "includeNutrition": True},
        ).json()
        results.append(details)
    return results


# ------------------------
# 💰 Price Helpers
# ------------------------

def extract_base_price(recipe: Dict) -> float:
    """Return price per serving in CHF (Spoonacular liefert Cents in USD)."""
    cents = recipe.get("pricePerServing", 0)  # US‑Cents
    return round(cents / 100, 2)  # ~USD → CHF


def calculate_price(base_price: float, rating: float) -> float:
    """Dynamic price: teurer bei hoher, günstiger bei niedriger Bewertung."""
    if base_price == 0:
        return 0.0
    if rating >= 4.5:
        return round(base_price * 1.2, 2)
    if rating < 3.0:
        return round(base_price * 0.9, 2)
    return round(base_price, 2)


# ------------------------
# 🧠 Session State Init
# ------------------------

if "recipe_ratings" not in st.session_state:
    # recipe_id -> {title, image, calories, base_price, ratings: List[float]}
    st.session_state.recipe_ratings: Dict[int, Dict] = {}

if "recipes" not in st.session_state:
    st.session_state.recipes: List[Dict] = []  # last search result

if "favorite_recipes" not in st.session_state:
    st.session_state.favorite_recipes: Dict[int, Dict] = {}


# ------------------------
# 🧠 Rating & Helper Functions
# ------------------------

def save_rating(recipe: Dict, rating: float) -> None:
    rid = recipe["id"]
    entry = st.session_state.recipe_ratings.setdefault(
        rid,
        {
            "title": recipe["title"],
            "image": recipe["image"],
            "calories": extract_calories(recipe),
            "base_price": extract_base_price(recipe),
            "ratings": [],
        },
    )
    entry["ratings"].append(rating)


def bayesian_average(ratings: List[float], C: float = 3.5, m: int = 5) -> float:
    n = len(ratings)
    if n == 0:
        return 0.0
    avg = sum(ratings) / n
    return (m * C + n * avg) / (m + n)


def extract_calories(recipe: Dict) -> float:
    macros = {n["name"]: n["amount"] for n in recipe["nutrition"]["nutrients"]}
    return macros.get("Calories", 0.0)


# --- Composite Dish‑of‑The‑Day Scoring --------------------------------------

WEIGHT_RATING = 0.5
WEIGHT_PRICE = 0.3
WEIGHT_CAL = 0.2


def _normalise(value: float, v_min: float, v_max: float, reverse: bool = False) -> float:
    if v_max == v_min:
        return 1.0
    norm = (value - v_min) / (v_max - v_min)
    return 1 - norm if reverse else norm


def _normalise_series(series: pd.Series, reverse: bool = False) -> pd.Series:
    if series.max() == series.min():
        return pd.Series(1.0, index=series.index)
    norm = (series - series.min()) / (series.max() - series.min())
    return 1 - norm if reverse else norm


def build_score_df() -> pd.DataFrame:
    """DataFrame aller bewerteten Gerichte inkl. Preis aus API."""
    rows = []
    for rid, e in st.session_state.recipe_ratings.items():
        if not e["ratings"]:
            continue
        bayes = bayesian_average(e["ratings"])
        price_after_rating = calculate_price(e["base_price"], bayes)
        rows.append(
            {
                "id": rid,
                "title": e["title"],
                "image": e["image"],
                "calories": e["calories"],
                "bayes_rating": bayes,
                "price": price_after_rating,
            }
        )
    df = pd.DataFrame(rows)
    if df.empty:
        return df

    df["norm_rating"] = _normalise_series(df["bayes_rating"])
    df["norm_price"] = _normalise_series(df["price"], reverse=True)
    df["norm_cal"] = _normalise_series(df["calories"], reverse=True)
    df["score"] = (
        WEIGHT_RATING * df["norm_rating"]
        + WEIGHT_PRICE * df["norm_price"]
        + WEIGHT_CAL * df["norm_cal"]
    )
    return df


def choose_dish_of_the_day(df: pd.DataFrame) -> Tuple[Dict | None, float]:
    if df.empty:
        return None, 0.0
    best_row = df.loc[df["score"].idxmax()]
    return best_row.to_dict(), best_row["score"]


# ------------------------
# 🚀 Streamlit UI
# ------------------------

st.set_page_config(page_title="SmartMeal 🍽️", layout="centered")
st.title("SmartMeal 🍽️ – Macro‑Aware Recipe Finder")

# 🥩 Macro Filters Sidebar
st.sidebar.header("Macro Filters")
min_protein = st.sidebar.slider("Min. Protein (g)", 0, 100, 25)
max_calories = st.sidebar.slider("Max. Calories", 100, 1500, 600)
number = st.sidebar.slider("Number of Meals", 1, 10, 3)

# 🎲 Surprise‑Me Button (sidebar)
if st.sidebar.button("🎲 Surprise me"):
    pool = list(st.session_state.favorite_recipes.values()) or st.session_state.recipes
    if not pool:
        st.sidebar.warning("Keine Gerichte vorhanden – bitte zuerst suchen.")
    else:
        surprise = random.choice(pool)
        st.sidebar.markdown("## 🪄 Dein Zufallsvorschlag:")
        st.sidebar.write(surprise["title"])
        st.sidebar.image(surprise["image"], width=200)
        kcal = extract_calories(surprise)
        st.sidebar.caption(f"{kcal:.0f} kcal • {extract_base_price(surprise):.2f} {PRICE_CURRENCY}")

# 🔍 Search
if st.button("🔍 Search Meals with Filters"):
    st.session_state.recipes = search_recipes_by_protein(
        min_protein=min_protein, max_calories=max_calories, number=number
    )

# 🍽️ List Results
if not st.session_state.recipes:
    st.info("Benutze die Suche, um passende Gerichte zu finden.")
else:
    for recipe in st.session_state.recipes:
        rid = recipe["id"]
        title = recipe["title"]
        image = recipe["image"]
        base_price = extract_base_price(recipe)

        with st.container():
            cols = st.columns([2, 1])
            with cols[0]:
                st.subheader(title)
                st.image(image, width=300)
            with cols[1]:
                fav_state = rid in st.session_state.favorite_recipes
                fav_label = "★ Entfernen" if fav_state else "☆ Favorit"
                if st.button(fav_label, key=f"fav_{rid}"):
                    if fav_state:
                        st.session_state.favorite_recipes.pop(rid)
                    else:
                        st.session_state.favorite_recipes[rid] = recipe

            kcal = extract_calories(recipe)
            macros = {n["name"]: n["amount"] for n in recipe["nutrition"]["nutrients"]}
            protein = macros.get("Protein", 0)
            fat = macros.get("Fat", 0)
            carbs = macros.get("Carbohydrates", 0)

            st.markdown(
                f"🧪 **Calories:** {kcal:.0f} kcal  |  💪 **Protein:** {protein:.1f} g  |  🥈 **Fat:** {fat:.1f} g  |  🥖 **Carbs:** {carbs:.1f} g  |  💰 **Preis:** {base_price:.2f} {PRICE_CURRENCY}"
            )

            # Rating Form
            with st.form(key=f"form_{rid}"):
                rating = st.slider("🧑‍🏫 Deine Bewertung", 1.0, 5.0, 4.0, 0.5, key=f"rating_{rid}")
                new_price = calculate_price(base_price, rating)
                st.markdown(f"💰 **Preis nach Rating:** {new_price:.2f} {PRICE_CURRENCY}")
                submitted = st.form_submit_button("✅ Bewertung speichern")
                if submitted:
                    save_rating(recipe, rating)
                    st.success("Rating gespeichert! 👌")

            st.markdown("---")

# ⭐ Dish of the Day & Visualisation
score_df = build_score_df()
auto_best, auto_score = choose_dish_of_the_day(score_df)

if auto_best:
    st.header("💡 Gericht des Tages")
    st.subheader(auto_best["title"])
    st.image(auto_best["image"], width=350)
    st.markdown(
        f"👉 **Gesamtscore:** {auto_score:.2%}\n\n"
        f"⭐️ Bayes‑Rating: {auto_best['bayes_rating']:.2f} / 5\n"
        f"💰 Preis (mit Rating): {auto_best['price']:.2f} {PRICE_CURRENCY}\n"
        f"🔥 Kalorien: {extract_calories(auto_best):.0f} kcal"
    )

# 📊 Vergleichs‑Visualisierung aller bewerteten Gerichte
if not score_df.empty:
    st.subheader("📊 Score‑Vergleich aller bewerteten Gerichte")
    chart = (
        alt.Chart(score_df)
        .mark_bar()
        .encode(
            x=alt.X("score:Q", title="Composite Score (0‑1)"),
            y=alt.Y("title:N", sort="-x", title="Gericht"),
            color=alt.condition(
                alt.datum.title == auto_best.get("title", ""), alt.value("#ffbf00"), alt.value("#3182bd")
            ),
            tooltip=[
                alt.Tooltip("title:N", title="Gericht"),
                alt.Tooltip("bayes_rating:Q", title="Bayes‑Rating", format=".2f"),
                alt.Tooltip("price:Q", title=f"Preis ({PRICE_CURRENCY})", format=".2f"),
                alt.Tooltip("calories:Q", title="Kalorien", format=".0f"),
                alt.Tooltip("score:Q", title="Score", format=".2%"),
            ],
        )
        .properties(height=300)
    )
    st.altair_chart(chart, use_container_width=True)


