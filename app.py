import requests
import streamlit as st
import math

# ------------------------
# 🔐 Spoonacular API Key
# ------------------------
API_KEY = "37b9d6cf14e549739544c7a1eb1ca971"

# ------------------------
# 🔍 Search for meals by keyword
# ------------------------

def search_meal(query):
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

def search_recipes_by_protein(min_protein=25, max_calories=None, number=5):
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

def calculate_price(base_price, rating):
    if rating >= 4.5:
        return round(base_price * 1.2, 2)
    elif rating < 3.0:
        return round(base_price * 0.9, 2)
    return round(base_price, 2)


# ------------------------
# 🧠 Ratings Handling & Dish‑of‑the‑Day Algorithm
# ------------------------

# Persist ratings across reruns
if "recipe_ratings" not in st.session_state:
    # recipe_id -> {"title": str, "image": str, "ratings": [float]}
    st.session_state.recipe_ratings = {}


def save_rating(recipe_id: int, title: str, image: str, rating: float) -> None:
    """Store the rating in session_state."""
    entry = st.session_state.recipe_ratings.setdefault(
        recipe_id, {"title": title, "image": image, "ratings": []}
    )
    entry["ratings"].append(rating)


def bayesian_average(ratings: list[float], C: float = 3.5, m: int = 5) -> float:
    """Return the Bayesian‑adjusted average to avoid small‑sample bias."""
    n = len(ratings)
    if n == 0:
        return 0.0
    avg = sum(ratings) / n
    return (m * C + n * avg) / (m + n)


def get_dish_of_the_day():
    """Pick the recipe with the highest Bayesian score."""
    best_score, best_entry = -1, None
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

# ⭐ Show Dish of the Day (if any ratings exist)
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

# 🔍 Trigger search
if st.button("🔍 Search Meals with Filters"):
    recipes = search_recipes_by_protein(min_protein, max_calories, number)

    if not recipes:
        st.warning("No matching meals found.")
    else:
        for recipe in recipes:
            rid = recipe["id"]
            title = recipe["title"]
            image = recipe["image"]

            with st.container():
                st.subheader(title)
                st.image(image, width=300)

                # Nutrition table
                macros = {n["name"]: n["amount"] for n in recipe["nutrition"]["nutrients"]}
                kcal = macros.get("Calories", 0)
                protein = macros.get("Protein", 0)
                fat = macros.get("Fat", 0)
                carbs = macros.get("Carbohydrates", 0)

                st.markdown(f"🧪 **Calories:** {kcal:.0f} kcal")
                st.markdown(f"💪 **Protein:** {protein:.1f} g")
                st.markdown(f"🥈 **Fat:** {fat:.1f} g")
                st.markdown(f"🥖 **Carbohydrates:** {carbs:.1f} g")

                # Rating input
                rating = st.slider(
                    f"🧑‍🏫 Your rating for {title}",
                    1.0,
                    5.0,
                    4.0,
                    0.5,
                    key=f"rating_{rid}",
                )
                new_price = calculate_price(10, rating)
                st.markdown(f"💰 **Price after rating:** {new_price:.2f} CHF")

                if st.button(f"✅ Save rating for {title}", key=f"save_{rid}"):
                    save_rating(rid, title, image, rating)
                    st.success("Rating saved! 👌")
