import requests
import streamlit as st
from typing import List, Dict

# ------------------------
# 🔐 Spoonacular API Key
# ------------------------
API_KEY = "37b9d6cf14e549739544c7a1eb1ca971"

# ------------------------
# 🔍 Search for meals by keyword
# ------------------------

def search_meal(query: str) -> List[Dict]:
    url = "https://api.spoonacular.com/recipes/complexSearch"
    params = {
        "query": query,
        "number": 5,
        "addRecipeInformation": True,
        "apiKey": API_KEY,
    }
    response = requests.get(url, params=params)
    return response.json().get("results", [])


# ------------------------
# 📊 Filter meals by protein and calories
# ------------------------

def search_recipes_by_protein(
    min_protein: int = 25, max_calories: int | None = None, number: int = 5
) -> List[Dict]:
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
# 💰 Dynamic price logic
# ------------------------

def calculate_price(base_price: float, rating: float) -> float:
    if rating >= 4.5:
        return round(base_price * 1.2, 2)
    if rating < 3.0:
        return round(base_price * 0.9, 2)
    return round(base_price, 2)


# ------------------------
# 🧠 Ratings Handling & Dish‑of‑the‑Day Algorithm
# ------------------------

if "recipe_ratings" not in st.session_state:
    # recipe_id -> {"title": str, "image": str, "ratings": [float]}
    st.session_state.recipe_ratings: Dict[int, Dict] = {}

if "recipes" not in st.session_state:
    st.session_state.recipes: List[Dict] = []  # last search result


def save_rating(recipe_id: int, title: str, image: str, rating: float) -> None:
    entry = st.session_state.recipe_ratings.setdefault(
        recipe_id, {"title": title, "image": image, "ratings": []}
    )
    entry["ratings"].append(rating)


def bayesian_average(ratings: List[float], C: float = 3.5, m: int = 5) -> float:
    n = len(ratings)
    if n == 0:
        return 0.0
    avg = sum(ratings) / n
    return (m * C + n * avg) / (m + n)


def get_dish_of_the_day():
    best_score, best_entry = -1.0, None
    for entry in st.session_state.recipe_ratings.values():
        score = bayesian_average(entry["ratings"])
        if score > best_score:
            best_score, best_entry = score, entry
    return best_entry, best_score


# ------------------------
# 🚀 Streamlit App
# ------------------------

st.set_page_config(page_title="SmartMeal 🍽️", layout="centered")
st.title("SmartMeal 🍽️ – Macro‑Aware Recipe Finder")

# ⭐ Dish of the Day (persisted across reruns)
dish, score = get_dish_of_the_day()
if dish:
    st.header("⭐ Gericht des Tages")
    st.subheader(dish["title"])
    st.image(dish["image"], width=350)
    st.markdown(f"Durchschnittsbewertung (Bayes): **{score:.2f} / 5**")
    st.markdown("---")

# 🥩 Macro Filters Sidebar
st.sidebar.header("Macro Filters")
min_protein = st.sidebar.slider("Min. Protein (g)", 0, 100, 25)
max_calories = st.sidebar.slider("Max. Calories", 100, 1500, 600)
number = st.sidebar.slider("Number of Meals", 1, 10, 3)

# 🔍 Trigger search – store result in session_state
action_search = st.button("🔍 Search Meals with Filters")
if action_search:
    st.session_state.recipes = search_recipes_by_protein(
        min_protein=min_protein, max_calories=max_calories, number=number
    )

# 🖼️ Show current search result (if any)
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

            # Nutrition
            macros = {n["name"]: n["amount"] for n in recipe["nutrition"]["nutrients"]}
            kcal = macros.get("Calories", 0)
            protein = macros.get("Protein", 0)
            fat = macros.get("Fat", 0)
            carbs = macros.get("Carbohydrates", 0)

            st.markdown(
                f"🧪 **Calories:** {kcal:.0f} kcal  |  💪 **Protein:** {protein:.1f} g  |  🥈 **Fat:** {fat:.1f} g  |  🥖 **Carbs:** {carbs:.1f} g"
            )

            # --- Rating Form (avoids collapsing on submit) ---
            with st.form(key=f"form_{rid}"):
                rating = st.slider(
                    "🧑‍🏫 Deine Bewertung", 1.0, 5.0, 4.0, 0.5, key=f"rating_{rid}"
                )
                new_price = calculate_price(10, rating)
                st.markdown(f"💰 **Preis nach Rating:** {new_price:.2f} CHF")

                submitted = st.form_submit_button("✅ Bewertung speichern")
                if submitted:
                    save_rating(rid, title, image, rating)
                    st.success("Rating gespeichert! 👌")

            st.markdown("---")
