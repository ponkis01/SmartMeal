import random
import requests
import streamlit as st
import pandas as pd
import altair as alt
from typing import List, Dict, Tuple, Optional

# ------------------------
# 🔐 Spoonacular API Key
# ------------------------
API_KEY = "37b9d6cf14e549739544c7a1eb1ca971"
PRICE_CURRENCY = "CHF"  # Treat Spoonacular USD as CHF for demo

# ------------------------
# 🔧 Spoonacular helpers
# ------------------------

def _get(url: str, params: Optional[Dict] = None) -> Dict:
    p = {"apiKey": API_KEY}
    if params:
        p.update(params)
    return requests.get(url, params=p, timeout=15).json()


def fetch_recipe_info(recipe_id: int) -> Dict:
    return _get(
        f"https://api.spoonacular.com/recipes/{recipe_id}/information",
        {"includeNutrition": True},
    )


def fetch_similar_recipes(
    recipe_id: int, *, number: int = 6, exclude_ids: Optional[set] = None
) -> List[Dict]:
    """Return *detailed* info for recipes similar to recipe_id (excluding duplicates)."""
    exclude_ids = exclude_ids or set()
    sims = _get(
        f"https://api.spoonacular.com/recipes/{recipe_id}/similar",
        {"number": number},
    )
    results = []
    for sim in sims:
        rid = sim.get("id")
        if rid in exclude_ids:
            continue
        try:
            details = fetch_recipe_info(rid)
            results.append(details)
        except Exception:
            continue
    return results


def search_recipes_by_protein(
    min_protein: int = 25, max_calories: Optional[int] = None, number: int = 5
) -> List[Dict]:
    params = {
        "minProtein": min_protein,
        "number": number,
        "addRecipeInformation": False,
    }
    if max_calories:
        params["maxCalories"] = max_calories
    res = _get("https://api.spoonacular.com/recipes/complexSearch", params)
    out: List[Dict] = []
    for r in res.get("results", []):
        out.append(fetch_recipe_info(r["id"]))
    return out

# ------------------------
# 💰 Price helpers
# ------------------------

def extract_base_price(recipe: Dict) -> float:
    cents = recipe.get("pricePerServing", 0)
    return round(cents / 100, 2)


def calculate_price(base_price: float, rating: float) -> float:
    if base_price == 0:
        return 0.0
    if rating >= 4.5:
        return round(base_price * 1.2, 2)
    if rating < 3.0:
        return round(base_price * 0.9, 2)
    return round(base_price, 2)

# ------------------------
# 🧠 Session state init
# ------------------------

if "recipe_ratings" not in st.session_state:
    st.session_state.recipe_ratings: Dict[int, Dict] = {}
if "recipes" not in st.session_state:
    st.session_state.recipes: List[Dict] = []
if "favorite_recipes" not in st.session_state:
    st.session_state.favorite_recipes: Dict[int, Dict] = {}

# ------------------------
# 🔬 metrics helpers
# ------------------------

def bayesian_average(ratings: List[float], C: float = 3.5, m: int = 5) -> float:
    n = len(ratings)
    if n == 0:
        return 0.0
    return (m * C + n * (sum(ratings) / n)) / (m + n)


def extract_calories(recipe: Dict) -> float:
    for n in recipe.get("nutrition", {}).get("nutrients", []):
        if n["name"] == "Calories":
            return n["amount"]
    return 0.0

# composite score weights
WEIGHT_RATING = 0.5
WEIGHT_PRICE = 0.3
WEIGHT_CAL = 0.2


def _norm_series(series: pd.Series, reverse: bool = False) -> pd.Series:
    if series.max() == series.min():
        return pd.Series(1.0, index=series.index)
    res = (series - series.min()) / (series.max() - series.min())
    return 1 - res if reverse else res


def build_score_df() -> pd.DataFrame:
    rows = []
    for rid, e in st.session_state.recipe_ratings.items():
        if not e["ratings"]:
            continue
        bayes = bayesian_average(e["ratings"])
        price = calculate_price(e["base_price"], bayes)
        rows.append(
            {
                "id": rid,
                "title": e["title"],
                "image": e["image"],
                "calories": e["calories"],
                "bayes_rating": bayes,
                "price": price,
            }
        )
    df = pd.DataFrame(rows)
    if df.empty:
        return df
    df["norm_rating"] = _norm_series(df["bayes_rating"])
    df["norm_price"] = _norm_series(df["price"], reverse=True)
    df["norm_cal"] = _norm_series(df["calories"], reverse=True)
    df["score"] = (
        WEIGHT_RATING * df["norm_rating"]
        + WEIGHT_PRICE * df["norm_price"]
        + WEIGHT_CAL * df["norm_cal"]
    )
    return df


def choose_dish_of_the_day(df: pd.DataFrame) -> Tuple[Optional[Dict], float]:
    if df.empty:
        return None, 0.0
    row = df.loc[df["score"].idxmax()]
    return row.to_dict(), row["score"]

# ------------------------
# 🚀 Streamlit UI
# ------------------------

st.set_page_config(page_title="SmartMeal 🍽️", layout="centered")
st.title("SmartMeal 🍽️ – Macro-Aware Recipe Finder")

# sidebar filters
st.sidebar.header("Macro Filters")
min_protein = st.sidebar.slider("Min. Protein (g)", 0, 100, 25)
max_calories = st.sidebar.slider("Max. Calories", 100, 1500, 600)
number = st.sidebar.slider("Number of Meals", 1, 10, 3)

# 🎲 Surprise-me logic (similar recipe)
if st.sidebar.button("🎲 Surprise me"):
    if not st.session_state.favorite_recipes:
        st.sidebar.warning("Du hast noch keine Favoriten gespeichert.")
    else:
        seed_recipe = random.choice(list(st.session_state.favorite_recipes.values()))
        similar = fetch_similar_recipes(
            seed_recipe["id"], exclude_ids=set(st.session_state.favorite_recipes.keys())
        )
        if not similar:
            st.sidebar.info("Keine ähnlichen Gerichte gefunden, versuche es später erneut.")
        else:
            choice = random.choice(similar)
            st.sidebar.markdown("## 🪄 Zufälliges ähnliches Gericht")
            st.sidebar.write(choice["title"])
            st.sidebar.image(choice["image"], width=200)
            st.sidebar.caption(
                f"{extract_calories(choice):.0f} kcal • {extract_base_price(choice):.2f} {PRICE_CURRENCY}"
            )

# search button
if st.button("🔍 Search Meals with Filters"):
    st.session_state.recipes = search_recipes_by_protein(
        min_protein=min_protein, max_calories=max_calories, number=number
    )

# list recipes
if not st.session_state.recipes:
    st.info("Benutze die Suche, um passende Gerichte zu finden.")
else:
    for rec in st.session_state.recipes:
        rid = rec["id"]
        base_price = extract_base_price(rec)
        with st.container():
            cols = st.columns([2, 1])
            with cols[0]:
                st.subheader(rec["title"])
                st.image(rec["image"], width=300)
            with cols[1]:
                fav = rid in st.session_state.favorite_recipes
                label = "★ Entfernen" if fav else "☆ Favorit"
                if st.button(label, key=f"fav_{rid}"):
                    if fav:
                        st.session_state.favorite_recipes.pop(rid)
                    else:
                        st.session_state.favorite_recipes[rid] = rec
            kcal = extract_calories(rec)
            macros = {n["name"]: n["amount"] for n in rec["nutrition"]["nutrients"]}
            st.markdown(
                f"🧪 **Calories:** {kcal:.0f} kcal | 💪 Protein: {macros.get('Protein',0):.1f} g | 💰 Preis: {base_price:.2f} {PRICE_CURRENCY}"
            )
            with st.form(key=f"form_{rid}"):
                rating = st.slider("🧑‍🏫 Deine Bewertung", 1.0, 5.0, 4.0, 0.5, key=f"rate_{rid}")
                dyn_price = calculate_price(base_price, rating)
                st.markdown(f"💰 Preis nach Rating: {dyn_price:.2f} {PRICE_CURRENCY}")
                if st.form_submit_button("✅ Bewertung speichern"):
                    st.session_state.recipe_ratings.setdefault(
                        rid,
                        {
                            "title": rec["title"],
                            "image": rec["image"],
                            "calories": kcal,
                            "base_price": base_price,
                            "ratings": [],
                        },
                    )["ratings"].append(rating)
                    st.success("Rating gespeichert!")
            st.markdown("---")

# Dish of the day
score_df = build_score_df()
best, best_score = choose_dish_of_the_day(score_df)
if best:
    st.header("💡 Gericht des Tages")
    st.subheader(best["title"])
    st.image(best["image"], width=350)
    st.markdown(
        f"⭐️ Score: {best_score:.2%} | Bayes: {best['bayes_rating']:.2f} | Preis: {best['price']:.2f} {PRICE_CURRENCY} | Kalorien: {best['calories']:.0f} kcal"
    )

# chart
if not score_df.empty:
    chart = (
        alt.Chart(score_df)
        .mark_bar()
        .encode(
            x=alt.X("score:Q", title="Composite Score"),
            y=alt.Y("title:N", sort="-x", title="Gericht"),
            tooltip=["bayes_rating:Q", "price:Q", "calories:Q", "score:Q"],
            color=alt.condition(alt.datum.title == (best or {}).get("title", ""), alt.value("#ffbf00"), alt.value("#3182bd")),
        )
        .properties(height=280)
    )
    st.subheader("📊 Bewertete Gerichte – Score")
    st.altair_chart(chart, use_container_width=True)
