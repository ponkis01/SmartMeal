import requests
import streamlit as st
from typing import List, Dict, Tuple

# ------------------------
# 🔐 Spoonacular API Key
# ------------------------
API_KEY = "37b9d6cf14e549739544c7a1eb1ca971"
BASE_PRICE = 10.0  # CHF

# ------------------------
# 🔍 Spoonacular Search
# ------------------------

def search_recipes_by_protein(
    min_protein: int = 25, max_calories: int | None = None, number: int = 5
) -> List[Dict]:
    """Query Spoonacular for high‑protein recipes and return full nutrition."""
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
# 💰 Price Logic
# ------------------------

def calculate_price(base_price: float, rating: float) -> float:
    if rating >= 4.5:
        return round(base_price * 1.2, 2)
    if rating < 3.0:
        return round(base_price * 0.9, 2)
    return round(base_price, 2)


# ------------------------
# 🧠 Rating & Scoring Helpers
# ------------------------

if "recipe_ratings" not in st.session_state:
    # recipe_id -> {title, image, calories, ratings: List[float]}
    st.session_state.recipe_ratings: Dict[int, Dict] = {}

if "recipes" not in st.session_state:
    st.session_state.recipes: List[Dict] = []  # last search result


def save_rating(recipe: Dict, rating: float) -> None:
    rid = recipe["id"]
    entry = st.session_state.recipe_ratings.setdefault(
        rid,
        {
            "title": recipe["title"],
            "image": recipe["image"],
            "calories": extract_calories(recipe),
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
        return 1.0  # avoid zero‑division, all equal
    norm = (value - v_min) / (v_max - v_min)
    return 1 - norm if reverse else norm


def choose_dish_of_the_day() -> Tuple[Dict | None, float]:
    """Return (entry, composite_score)."""
    entries = [e for e in st.session_state.recipe_ratings.values() if e["ratings"]]
    if not entries:
        return None, 0.0

    # collect metrics
    ratings_bayes = [bayesian_average(e["ratings"]) for e in entries]
    prices = [calculate_price(BASE_PRICE, r) for r in ratings_bayes]
    calories = [e["calories"] for e in entries]

    r_min, r_max = min(ratings_bayes), max(ratings_bayes)
    p_min, p_max = min(prices), max(prices)
    c_min, c_max = min(calories), max(calories)

    best, best_score = None, -1.0
    for e, r_b, p, c in zip(entries, ratings_bayes, prices, calories):
        score = (
            WEIGHT_RATING * _normalise(r_b, r_min, r_max)
            + WEIGHT_PRICE * _normalise(p, p_min, p_max, reverse=True)
            + WEIGHT_CAL * _normalise(c, c_min, c_max, reverse=True)
        )
        if score > best_score:
            best, best_score = e | {"bayes_rating": r_b, "price": p}, score
    return best, best_score


# ------------------------
# 🚀 Streamlit UI
# ------------------------

st.set_page_config(page_title="SmartMeal 🍽️", layout="centered")
st.title("SmartMeal 🍽️ – Macro-Aware Recipe Finder")

# 🥩 Macro Filters Sidebar
st.sidebar.header("Macro Filters")
min_protein = st.sidebar.slider("Min. Protein (g)", 0, 100, 25)
max_calories = st.sidebar.slider("Max. Calories", 100, 1500, 600)
number = st.sidebar.slider("Number of Meals", 1, 10, 3)

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

        with st.container():
            st.subheader(title)
            st.image(image, width=300)

            kcal = extract_calories(recipe)
            macros = {n["name"]: n["amount"] for n in recipe["nutrition"]["nutrients"]}
            protein = macros.get("Protein", 0)
            fat = macros.get("Fat", 0)
            carbs = macros.get("Carbohydrates", 0)

            st.markdown(
                f"🧪 **Calories:** {kcal:.0f} kcal  |  💪 **Protein:** {protein:.1f} g  |  🥈 **Fat:** {fat:.1f} g  |  🥖 **Carbs:** {carbs:.1f} g"
            )

            # Rating Form (isolated rerun)
            with st.form(key=f"form_{rid}"):
                rating = st.slider("🧑‍🏫 Deine Bewertung", 1.0, 5.0, 4.0, 0.5, key=f"rating_{rid}")
                new_price = calculate_price(BASE_PRICE, rating)
                st.markdown(f"💰 **Preis nach Rating:** {new_price:.2f} CHF")
                submitted = st.form_submit_button("✅ Bewertung speichern")
                if submitted:
                    save_rating(recipe, rating)
                    st.success("Rating gespeichert! 👌")

            st.markdown("---")

# ⭐ Dish of the Day – shown at the very end of the page
best, score = choose_dish_of_the_day()
if best:
    st.header("💡 Gericht des Tages")
    st.subheader(best["title"])
    st.image(best["image"], width=350)
    st.markdown(
        f"👉 **Gesamtscore:** {score:.2%}\n\n"
        f"⭐️ Bayes‑Rating: {best['bayes_rating']:.2f} / 5\n"
        f"💰 Preis (mit Rating): {best['price']:.2f} CHF\n"
        f"🔥 Kalorien: {best['calories']:.0f} kcal"
    )

