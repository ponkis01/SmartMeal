import requests
import streamlit as st

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
        "apiKey": API_KEY
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
        "addRecipeInformation": False
    }
    if max_calories:
        params["maxCalories"] = max_calories

    response = requests.get(search_url, params=params).json()
    results = []
    for recipe in response.get("results", []):
        r_id = recipe["id"]
        details = requests.get(
            f"https://api.spoonacular.com/recipes/{r_id}/information",
            params={"apiKey": API_KEY, "includeNutrition": True}
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
    else:
        return round(base_price, 2)

# ------------------------
# 🧠 Update rating
# ------------------------
def update_rating(meal, new_rating):
    meal["ratings"].append(new_rating)
    average = sum(meal["ratings"]) / len(meal["ratings"])
    meal["rating"] = round(average, 2)
    return meal

# ------------------------
# 🚀 Streamlit App
# ------------------------
st.set_page_config(page_title="SmartMeal 🍽️", layout="centered")
st.title("SmartMeal 🍽️ – Macro-Aware Recipe Finder")

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
            st.subheader(recipe["title"])
            st.image(recipe["image"], width=300)

            macros = {n["name"]: n["amount"] for n in recipe["nutrition"]["nutrients"]}
            kcal = macros.get("Calories", 0)
            protein = macros.get("Protein", 0)
            fat = macros.get("Fat", 0)
            carbs = macros.get("Carbohydrates", 0)

            st.markdown(f"🧪 **Calories:** {kcal:.0f} kcal")
            st.markdown(f"💪 **Protein:** {protein:.1f} g")
            st.markdown(f"🥈 **Fat:** {fat:.1f} g")
            st.markdown(f"🥖 **Carbohydrates:** {carbs:.1f} g")

            rating = st.slider(f"🧑‍🏫 Your rating for {recipe['title']}", 1.0, 5.0, 4.0, 0.5)
            new_price = calculate_price(10, rating)
            st.markdown(f"💰 **Price after rating:** {new_price:.2f} CHF")

            if st.button(f"✅ Save rating for {recipe['title']}"):
                st.success("Rating saved!")
