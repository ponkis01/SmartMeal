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
PRICE_CURRENCY = "CHF"  # Treat Spoonacular USD roughly as CHF

# ------------------------
# 🛠️ Low‑level helpers
# ------------------------

def _get(url: str, params: Optional[Dict] = None) -> Dict:
    base = {"apiKey": API_KEY}
    if params:
        base.update(params)
    return requests.get(url, params=base, timeout=15).json()


# ⬇️ SPOONACULAR FETCHERS ----------------------------------------------------

def fetch_recipe_info(recipe_id: int) -> Dict:
    """Full recipe info including nutrition & instructions."""
    return _get(
        f"https://api.spoonacular.com/recipes/{recipe_id}/information",
        {"includeNutrition": True},
    )


def fetch_similar_recipes(
    recipe_id: int, *, number: int = 6, exclude_ids: Optional[set] = None
) -> List[Dict]:
    exclude_ids = exclude_ids or set()
    sims = _get(
        f"https://api.spoonacular.com/recipes/{recipe_id}/similar",
        {"number": number},
    )
    out: List[Dict] = []
    for s in sims:
        rid = s.get("id")
        if rid in exclude_ids:
            continue
        try:
            out.append(fetch_recipe_info(rid))
        except Exception:
            continue
    return out


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
    data = _get("https://api.spoonacular.com/recipes/complexSearch", params)
    return [fetch_recipe_info(r["id"]) for r in data.get("results", [])]

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
# 🧠 Session State init
# ------------------------

if "recipe_ratings" not in st.session_state:
    st.session_state.recipe_ratings: Dict[int, Dict] = {}
if "recipes" not in st.session_state:
    st.session_state.recipes: List[Dict] = []
if "favorite_recipes" not in st.session_state:
    st.session_state.favorite_recipes: Dict[int, Dict] = {}

# ------------------------
# 🔬 Metrics helpers
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

# Composite‑score weights
WEIGHT_RATING = 0.5
WEIGHT_PRICE = 0.3
WEIGHT_CAL = 0.2


def _norm(series: pd.Series, reverse: bool = False) -> pd.Series:
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
    df["norm_rating"] = _norm(df["bayes_rating"])
    df["norm_price"] = _norm(df["price"], reverse=True)
    df["norm_cal"] = _norm(df["calories"], reverse=True)
    df["score"] = (
        WEIGHT_RATING * df["norm_rating"]
        + WEIGHT_PRICE * df["norm_price"]
        + WEIGHT_CAL * df["norm_cal"]
    )
    return df


def choose_dish_of_the_day(df: pd.DataFrame) -> Tuple[Optional[Dict], float]:
    if df.empty:
        return None, 0.0
    best = df.loc[df["score"].idxmax()]
    return best.to_dict(), best["score"]

# ------------------------
# 🍳 INSTRUCTION RENDERER
# ------------------------

def render_instructions(recipe: Dict) -> None:
    """Display step‑by‑step cooking instructions inside an expander."""
    instructions = recipe.get("analyzedInstructions", [])
    if not instructions:
        st.info("No instructions provided for this recipe.")
        return

    for block in instructions:
        steps = block.get("steps", [])
        for step in steps:
            num = step.get("number")
            text = step.get("step", "")
            st.markdown(f"**Step {num}.** {text}")
            if length := step.get("length"):
                st.caption(f"⏱ {length['number']} {length['unit']}")

# ------------------------
# 🚀 Streamlit UI
# ------------------------

st.set_page_config(page_title="SmartMeal 🍽️", layout="centered")
st.title("SmartMeal 🍽️ – Macro‑Aware Recipe Finder")

# Sidebar filters
st.sidebar.header("Macro Filters")
min_protein = st.sidebar.slider("Min. Protein (g)", 0, 100, 25)
max_calories = st.sidebar.slider("Max. Calories", 100, 1500, 600)
number = st.sidebar.slider("Number of Meals", 1, 10, 3)

# 🎲 Surprise‑me (similar recipe)
if st.sidebar.button("🎲 Surprise me with something similar"):
    if not st.session_state.favorite_recipes:
        st.sidebar.warning("You haven't saved any favorites yet.")
    else:
        seed = random.choice(list(st.session_state.favorite_recipes.values()))
        similar = fetch_similar_recipes(seed["id"], exclude_ids=set(st.session_state.favorite_recipes))
        if not similar:
            st.sidebar.info("No similar dishes found – try again later.")
        else:
            pick = random.choice(similar)
            st.sidebar.markdown("## ✨ Random similar dish")
            st.sidebar.write(pick["title"])
            st.sidebar.image(pick["image"], width=200)
            st.sidebar.caption(
                f"{extract_calories(pick):.0f} kcal • {extract_base_price(pick):.2f} {PRICE_CURRENCY}"
            )

# Trigger search
if st.button("🔍 Search meals with filters"):
    st.session_state.recipes = search_recipes_by_protein(
        min_protein=min_protein, max_calories=max_calories, number=number
    )

# Recipe list ----------------------------------------------------------------
if not st.session_state.recipes:
    st.info("Use the search to find matching dishes.")
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
                label = "★ Remove" if fav else "☆ Favorite"
                if st.button(label, key=f"fav_{rid}"):
                    if fav:
                        st.session_state.favorite_recipes.pop(rid)
                    else:
                        st.session_state.favorite_recipes[rid] = rec
            kcal = extract_calories(rec)
            macros = {n["name"]: n["amount"] for n in rec["nutrition"]["nutrients"]}
            st.markdown(
                f"🧪 **Calories:** {kcal:.0f} kcal | 💪 Protein: {macros.get('Protein', 0):.1f} g | 💰 Price: {base_price:.2f} {PRICE_CURRENCY}"
            )

            # Rating form
            with st.form(key=f"form_{rid}"):
                rating = st.slider("🧑‍🏫 Your rating", 1.0, 5.0, 4.0, 0.5, key=f"rate_{rid}")
                dyn_price = calculate_price(base_price, rating)
                st.markdown(f"💰 Price after rating: {dyn_price:.2f} {PRICE_CURRENCY}")
                if st.form_submit_button("✅ Save rating"):
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
                    st.success("Rating saved!")

            # Cooking instructions expander
            with st.expander("👩‍🍳 Show cooking instructions"):
                render_instructions(rec)

            st.markdown("---")

# Dish of the day -------------------------------------------------------------
score_df = build_score_df()
best, best_score = choose_dish_of_the_day(score_df)
if best:
    st.header("🌟 Dish of the Day")
    st.subheader(best["title"])
    st.image(best["image"], width=350)
    st.markdown(
        f"**Composite Score:** {best_score:.2%}\n\n"
        f"⭐ Bayes rating: {best['bayes_rating']:.2f} / 5\n"
        f"💰 Price (after rating): {best['price']:.2f} {PRICE_CURRENCY}\n"
        f"🔥 Calories: {best['calories']:.0f} kcal"
    )

# Score chart -----------------------------------------------------------------
if not score_df.empty:
    st.subheader("📊 Rated dishes – composite score")
    chart = (
        alt.Chart(score_df)
        .mark_bar()
        .encode(
            x=alt.X("score:Q", title="Composite score (0-1)"),
            y=alt.Y("title:N", sort="-x", title="Dish"),
            color=alt.condition(
                alt.datum.title == best.get("title", ""), alt.value("#ffbf00"), alt.value("#3182bd")
            ),
            tooltip=[
                alt.Tooltip("title:N", title="Dish"),
                alt.Tooltip("bayes_rating:Q", title="Bayes rating", format=".2f"),
                alt.Tooltip("price:Q", title=f"Price ({PRICE_CURRENCY})", format=".2f"),
                alt.Tooltip("calories:Q", title="Calories", format=".0f"),
                alt.Tooltip("score:Q", title="Score", format=".2%"),
            ],
        )
        .properties(height=280)
    )
    st.altair_chart(chart, use_container)