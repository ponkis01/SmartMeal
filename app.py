import random
# Imports random module for selecting random recipes in "Surprise me" mode.

import requests
# Imports requests library to make HTTP requests to Spoonacular API for fetching recipe data.

import streamlit as st
# Imports Streamlit, the UI framework for building the interactive web interface.

import pandas as pd
# Imports Pandas for data manipulation, creating DataFrames for recipe ratings and metrics.

import altair as alt
# Imports Altair for interactive visualizations like bar charts and line plots.

from typing import List, Dict, Tuple, Optional
# Imports type hints to enhance code readability by specifying expected data types.

# ------------------------
# 🔐 Spoonacular API Key
# ------------------------
# Section defines configuration variables for Spoonacular API and pricing currency.

API_KEY = "af3d3f0206044a5a8fa852bec4ffd6a5"
# Stores Spoonacular API key, required to authenticate API requests.

PRICE_CURRENCY = "CHF"  # Treat Spoonacular USD roughly as CHF
# Defines currency (Swiss Franc) for prices; Spoonacular USD treated as CHF.

# ------------------------
# 🛠️ Low‑level helpers
# ------------------------
# Section contains utility functions for Spoonacular API requests.

def _get(url: str, params: Optional[Dict] = None) -> Dict:
    # Function Overview: Low-level helper sending GET requests to Spoonacular API.
    # Simplifies API calls by handling API key and parameters.
    # Data Flow: Takes URL and optional parameters, sends request, returns JSON as dictionary.
    # Project Role: Used by higher-level functions to fetch recipe data.
    
    base = {"apiKey": API_KEY}
    # Creates dictionary with API key, required for all API requests.
    
    if params:
        base.update(params)
    # Merges additional parameters into base dictionary if provided.
    
    return requests.get(url, params=base, timeout=15).json()
    # Sends GET request with parameters and 15-second timeout, returns JSON response.
    # Data Flow: Response dictionary with recipe/search data passed to caller.

# ⬇️ SPOONACULAR FETCHERS ----------------------------------------------------
# Section contains functions fetching specific recipe data from Spoonacular API.

def fetch_recipe_info(recipe_id: int) -> Dict:
    # Function Overview: Fetches detailed information for a recipe by ID.
    # Retrieves recipe data, including nutrition and instructions.
    # Data Flow: Takes recipe ID, queries API, returns dictionary with details.
    # Project Role: Displays recipe details and extracts metrics like calories.
    # Parameter: recipe_id - Integer, unique ID of recipe in Spoonacular database.
    
    return _get(
        f"https://api.spoonacular.com/recipes/{recipe_id}/information",
        {"includeNutrition": True},
    )
    # Calls _get with recipe-specific URL and parameter for nutritional data.
    # Data Flow: API returns dictionary with title, image, nutrition, instructions.

def fetch_similar_recipes(
    recipe_id: int, *, number: int = 6, exclude_ids: Optional[set] = None
) -> List[Dict]:
    # Function Overview: Fetches recipes similar to given recipe by ID.
    # Supports "Surprise me" feature, suggesting similar recipes.
    # Data Flow: Takes recipe ID, queries API, fetches details, returns list of dictionaries.
    # Project Role: Suggests new recipes in sidebar for "Surprise me".
    # Parameter: recipe_id - ID of recipe to find similar recipes for.
    # Parameter: number - Number of similar recipes to fetch (default 6).
    # Parameter: exclude_ids - Optional set of recipe IDs to exclude.
    
    exclude_ids = exclude_ids or set()
    # Ensures exclude_ids is a set, initializing empty set if None.
    
    sims = _get(
        f"https://api.spoonacular.com/recipes/{recipe_id}/similar",
        {"number": number},
    )
    # Queries API for list of similar recipe IDs, limited to number.
    
    out: List[Dict] = []
    # Initializes empty list for detailed similar recipe information.
    
    for s in sims:
        # Iterates over similar recipe IDs from API.
        
        rid = s.get("id")
        # Extracts recipe ID from similar recipe data.
        
        if rid in exclude_ids:
            continue
        # Skips recipes in exclude_ids to avoid duplicates.
        
        try:
            out.append(fetch_recipe_info(rid))
        except Exception:
            continue
        # Fetches details for similar recipe, adds to output list.
        # Error Handling: Skips recipes failing to fetch due to errors.
    
    return out
    # Returns list of detailed recipe dictionaries for similar recipes.

def search_recipes_by_protein(
    min_protein: int = 25,
    max_protein: Optional[int] = None,
    min_calories: Optional[int] = None,
    max_calories: Optional[int] = None,
    number: int = 5
) -> List[Dict]:
    # Function Overview: Searches recipes by protein and calorie filters.
    # Finds recipes matching nutritional preferences, especially high-protein.
    # Data Flow: Takes filters, queries API, fetches details, returns recipe list.
    # Project Role: Powers main search, triggered by "Search meals with filters".
    # Parameter: min_protein - Minimum protein (grams, default 25).
    # Parameter: max_protein - Optional maximum protein (grams).
    # Parameter: min_calories - Optional minimum calories.
    # Parameter: max_calories - Optional maximum calories.
    # Parameter: number - Number of recipes to return (default 5).
    
    params = {
        "minProtein": min_protein,
        "number": number,
        "addRecipeInformation": False,
    }
    # Initializes dictionary with minimum protein and result count.
    # Note: addRecipeInformation False reduces initial payload; details fetched later.
    
    if max_protein:
        params["maxProtein"] = max_protein
    # Adds maximum protein filter if provided.
    
    if min_calories:
        params["minCalories"] = min_calories
    # Adds minimum calorie filter if provided.
    
    if max_calories:
        params["maxCalories"] = max_calories
    # Adds maximum calorie filter if provided.
    
    data = _get("https://api.spoonacular.com/recipes/complexSearch", params)
    # Queries API's complex search endpoint with filters.
    
    return [fetch_recipe_info(r["id"]) for r in data.get("results", [])]
    # Fetches details for each recipe ID in search results, returns list.
    # Data Flow: API returns recipe IDs, passed to fetch_recipe_info for details.

# ------------------------
# 💰 Price helpers
# ------------------------
# Section contains functions for calculating/adjusting recipe prices by ratings.

def extract_base_price(recipe: Dict) -> float:
    # Function Overview: Extracts base price per serving from recipe dictionary.
    # Provides initial price before dynamic rating adjustments.
    # Data Flow: Takes recipe dictionary, extracts price, returns float rounded to two decimals.
    # Project Role: Displays and calculates prices in UI.
    # Parameter: recipe - Dictionary with recipe data, including pricePerServing.
    
    cents = recipe.get("pricePerServing", 0)
    # Retrieves price per serving in cents, defaulting to 0 if unavailable.
    
    return round(cents / 100, 2)
    # Converts price from cents to dollars/CHF, rounds to two decimals.

def calculate_price(base_price: float, rating: float) -> float:
    # Function Overview: Applies dynamic pricing based on recipe rating.
    # Adjusts base price up/down by popularity (rating).
    # Data Flow: Takes base price and rating, applies multiplier, returns adjusted price.
    # Project Role: Shows rating impact on meal prices in UI.
    # Parameter: base_price - Original price per serving.
    # Parameter: rating - User or Bayesian-averaged rating (1.0-5.0).
    
    if base_price == 0:
        return 0.0
    # Returns 0 if base price is 0 to avoid invalid calculations.
    
    if rating >= 4.5:
        return round(base_price * 1.2, 2)
    # Increases price by 20% if rating is 4.5+, reflecting high popularity.
    
    if rating < 3.0:
        return round(base_price * 0.9, 2)
    # Decreases price by 10% if rating < 3.0, reflecting low popularity.
    
    return round(base_price, 2)
    # Returns unchanged base price if rating is 3.0-4.5.

# ------------------------
# 🧠 Session State init
# ------------------------
# Section initializes Streamlit session state for data persistence.

if "recipe_ratings" not in st.session_state:
    st.session_state.recipe_ratings: Dict[int, Dict] = {}
# Initializes dictionary for user ratings, recipe IDs as keys, details as values.
# Data Flow: Persists ratings for pricing and visualizations.

if "recipes" not in st.session_state:
    st.session_state.recipes: List[Dict] = []
# Initializes list for current recipes displayed post-search.
# Data Flow: Populated by search_recipes_by_protein, renders recipe cards.

if "favorite_recipes" not in st.session_state:
    st.session_state.favorite_recipes: Dict[int, Dict] = {}
# Initializes dictionary for user-favorited recipes, IDs as keys.
# Data Flow: Used in "Surprise me" to suggest similar recipes.

# ------------------------
# 🔬 Metrics helpers
# ------------------------
# Section contains functions for metrics like Bayesian averages and scores.

def bayesian_average(ratings: List[float], C: float = 3.5, m: int = 5) -> float:
    # Function Overview: Calculates Bayesian-weighted average rating.
    # Smooths ratings for low sample sizes, avoiding extreme values.
    # Data Flow: Takes ratings list, applies Bayesian formula, returns weighted average.
    # Project Role: Computes reliable ratings for pricing and "Dish of the Day".
    # Parameter: ratings - List of user ratings (1.0-5.0).
    # Parameter: C - Mean rating to regress toward (default 3.5).
    # Parameter: m - Weight of prior mean (default 5, like 5 average ratings).
    
    n = len(ratings)
    # Counts number of ratings provided.
    
    if n == 0:
        return 0.0
    # Returns 0 if no ratings to avoid division by zero.
    
    return (m * C + n * (sum(ratings) / n)) / (m + n)
    # Applies Bayesian formula: (m * C + n * mean) / (m + n).
    # Data Flow: Combines prior mean (C) with actual mean, weighted by m and n.

def extract_calories(recipe: Dict) -> float:
    # Function Overview: Extracts calorie content from recipe nutrition.
    # Provides calories for display and scoring.
    # Data Flow: Takes recipe dictionary, searches nutrition, returns calorie amount.
    # Project Role: Displays calories in UI, normalizes for scores.
    # Parameter: recipe - Dictionary with nutritional information.
    
    for n in recipe.get("nutrition", {}).get("nutrients", []):
        # Iterates over nutrients in recipe's nutrition data.
        
        if n["name"] == "Calories":
            return n["amount"]
        # Returns calorie amount if nutrient is "Calories".
    
    return 0.0
    # Returns 0 if no calorie information found.

# Composite‑score weights
WEIGHT_RATING = 0.5
# Weight (50%) for normalized rating in composite score.

WEIGHT_PRICE = 0.3
# Weight (30%) for normalized price in composite score.

WEIGHT_CAL = 0.2
# Weight (20%) for normalized calories in composite score.

def _norm(series: pd.Series, reverse: bool = False) -> pd.Series:
    # Function Overview: Normalizes Pandas Series to 0-1 range.
    # Scales values (ratings, prices, calories) for fair score comparison.
    # Data Flow: Takes Series, normalizes, returns new Series (0-1).
    # Project Role: Normalizes metrics for "Dish of the Day" in build_score_df.
    # Parameter: series - Numerical Pandas Series to normalize.
    # Parameter: reverse - If True, inverts normalization (higher values lower).
    
    if series.max() == series.min():
        return pd.Series(1.0, index=series.index)
    # Returns Series of 1.0 if values identical to avoid division by zero.
    
    res = (series - series.min()) / (series.max() - series.min())
    # Applies min-max normalization: (x - min) / (max - min).
    
    return 1 - res if reverse else res
    # Returns normalized Series, inverted if reverse (e.g., for price/calories).

def build_score_df() -> pd.DataFrame:
    # Function Overview: Builds DataFrame with composite scores for rated recipes.
    # Combines ratings, prices, calories into weighted score for "Dish of the Day".
    # Data Flow: Takes rated recipes, calculates normalized metrics/scores, returns DataFrame.
    # Project Role: Powers "Dish of the Day" and score visualization.
    
    rows = []
    # Initializes empty list for DataFrame rows.
    
    for rid, e in st.session_state.recipe_ratings.items():
        # Iterates over rated recipes in session state.
        
        if not e["ratings"]:
            continue
        # Skips recipes with no ratings to avoid empty data.
        
        bayes = bayesian_average(e["ratings"])
        # Calculates Bayesian-weighted average rating.
        
        price = calculate_price(e["base_price"], bayes)
        # Calculates dynamic price based on Bayesian rating.
        
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
        # Creates dictionary with recipe details/metrics, adds to rows.
    
    df = pd.DataFrame(rows)
    # Converts list of dictionaries to Pandas DataFrame.
    
    if df.empty:
        return df
    # Returns empty DataFrame if no rated recipes.
    
    df["norm_rating"] = _norm(df["bayes_rating"])
    # Normalizes Bayesian ratings to 0-1 (higher better).
    
    df["norm_price"] = _norm(df["price"], reverse=True)
    # Normalizes prices to 0-1, reversed (lower better).
    
    df["norm_cal"] = _norm(df["calories"], reverse=True)
    # Normalizes calories to 0-1, reversed (fewer better).
    
    df["score"] = (
        WEIGHT_RATING * df["norm_rating"]
        + WEIGHT_PRICE * df["norm_price"]
        + WEIGHT_CAL * df["norm_cal"]
    )
    # Calculates composite score as weighted sum of normalized metrics.
    
    return df
    # Returns DataFrame with recipe details and scores.

def choose_dish_of_the_day(df: pd.DataFrame) -> Tuple[Optional[Dict], float]:
    # Function Overview: Selects recipe with highest composite score as "Dish of the Day".
    # Identifies top recipe by rating, price, calories.
    # Data Flow: Takes score DataFrame, finds highest score, returns recipe and score.
    # Project Role: Highlights best recipe in UI.
    # Parameter: df - DataFrame with recipe details and scores.
    
    if df.empty:
        return None, 0.0
    # Returns None and 0.0 if DataFrame empty (no rated recipes).
    
    best = df.loc[df["score"].idxmax()]
    # Finds row with highest composite score using idxmax.
    
    return best.to_dict(), best["score"]
    # Returns tuple with best recipe dictionary and score.

# ------------------------
# 🍳 INSTRUCTION RENDERER
# ------------------------
# Section contains function to display cooking instructions.

def render_instructions(recipe: Dict) -> None:
    # Function Overview: Renders step-by-step cooking instructions in Streamlit expander.
    # Displays instructions to guide recipe preparation.
    # Data Flow: Takes recipe dictionary, extracts instructions, renders in UI.
    # Project Role: Enhances user experience with cooking guidance.
    # Parameter: recipe - Dictionary with analyzedInstructions.
    
    instructions = recipe.get("analyzedInstructions", [])
    # Retrieves instruction blocks from recipe dictionary.
    
    if not instructions:
        st.info("No instructions provided for this recipe.")
        return
    # Displays info message and exits if no instructions.
    
    for block in instructions:
        # Iterates over instruction blocks (e.g., preparation, cooking).
        
        steps = block.get("steps", [])
        # Retrieves steps within instruction block.
        
        for step in steps:
            # Iterates over each step in block.
            
            num = step.get("number")
            # Gets step number for display.
            
            text = step.get("step", "")
            # Gets step text description.
            
            st.markdown(f"**Step {num}.** {text}")
            # Renders step number and description using Markdown.
            
            if length := step.get("length"):
                st.caption(f"⏱ {length['number']} {length['unit']}")
            # Displays step duration as caption if available (e.g., "5 minutes").

# ------------------------
# 🚀 Streamlit UI
# ------------------------
# Section defines main Streamlit UI components, layout, filters, recipe displays.

st.set_page_config(page_title="SmartMeal 🍽️", layout="centered")
# Configures Streamlit page with title and centered layout.

st.title("SmartMeal 🍽️ – Macro‑Aware Recipe Finder")
# Displays main app title in UI.

# Sidebar filters
st.sidebar.header("Macro Filters")
# Adds header to sidebar for nutritional filter inputs.

protein_range = st.sidebar.slider("Protein (g)", 0, 90, (20, 60))
# Slider for protein range (0-90g), default 20-60g.
# Data Flow: Used in search_recipes_by_protein.

calorie_range = st.sidebar.slider("Calories", 100, 1500, (300, 750))
# Slider for calorie range (100-1500 kcal), default 300-750 kcal.
# Data Flow: Used in search_recipes_by_protein.

number = st.sidebar.slider("Number of Meals", 1, 10, 3)
# Slider for number of recipes (1-10), default 3.
# Data Flow: Limits results in search_recipes_by_protein.

min_protein, max_protein = protein_range
# Unpacks protein range tuple for search.

min_calories, max_calories = calorie_range
# Unpacks calorie range tuple for search.

# 🎲 Surprise‑me (similar recipe)
if st.sidebar.button("🎲 Surprise me with something similar"):
    # Button in sidebar for "Surprise me" feature.
    
    if not st.session_state.favorite_recipes:
        st.sidebar.warning("You haven't saved any favorites yet.")
    # Warns if no favorite recipes for suggestion.
    
    else:
        seed = random.choice(list(st.session_state.favorite_recipes.values()))
        # Randomly selects favorite recipe as seed.
        
        similar = fetch_similar_recipes(seed["id"], exclude_ids=set(st.session_state.favorite_recipes))
        # Fetches similar recipes, excluding favorites.
        
        if not similar:
            st.sidebar.info("No similar dishes found – try again later.")
        # Shows info message if no similar recipes.
        
        else:
            pick = random.choice(similar)
            # Randomly selects similar recipe to display.
            
            st.sidebar.markdown("## ✨ Random similar dish")
            # Adds subheader for suggested recipe.
            
            st.sidebar.write(pick["title"])
            # Displays suggested recipe title.
            
            st.sidebar.image(pick["image"], width=200)
            # Displays recipe image, 200px wide.
            
            st.sidebar.caption(
                f"{extract_calories(pick):.0f} kcal • {extract_base_price(pick):.2f} {PRICE_CURRENCY}"
            )
            # Displays calories and base price as caption.

# Trigger search
if st.button("🔍 Search meals with filters"):
    # Button to trigger recipe search with sidebar filters.
    
    st.session_state.recipes = search_recipes_by_protein(
        min_protein=min_protein,
        max_protein=max_protein,
        min_calories=min_calories,
        max_calories=max_calories,
        number=number
    )
    # Calls search_recipes_by_protein, stores results in session state.
    # Data Flow: Recipes populate UI recipe list.

# Recipe list ----------------------------------------------------------------
if not st.session_state.recipes:
    st.info("Use the search to find matching dishes.")
# Shows info message if no recipes (e.g., before search).
else:
    for rec in st.session_state.recipes:
        # Iterates over recipes in session state to display.
        
        rid = rec["id"]
        # Extracts recipe ID for ratings/favorites.
        
        base_price = extract_base_price(rec)
        # Calculates base price for display/pricing.
        
        with st.container():
            # Creates container for recipe UI elements.
            
            cols = st.columns([2, 1])
            # Splits layout into two columns (2:1) for details/favorite button.
            
            with cols[0]:
                st.subheader(rec["title"])
                # Displays recipe title as subheader.
                
                st.image(rec["image"], width=300)
                # Displays recipe image, 300px wide.
            
            with cols[1]:
                fav = rid in st.session_state.favorite_recipes
                # Checks if recipe is favorited.
                
                label = "★ Remove" if fav else "☆ Favorite"
                # Sets button label based on favorite status.
                
                if st.button(label, key=f"fav_{rid}"):
                    if fav:
                        st.session_state.favorite_recipes.pop(rid)
                    else:
                        st.session_state.favorite_recipes[rid] = rec
                # Button toggles favorite status, updates session state.
            
            kcal = extract_calories(rec)
            # Extracts calorie content for display.
            
            macros = {n["name"]: n["amount"] for n in rec["nutrition"]["nutrients"]}
            # Creates dictionary of macronutrient names/amounts.
            
            st.markdown(
                f"🧪 **Calories:** {kcal:.0f} kcal | 💪 Protein: {macros.get('Protein', 0):.1f} g | 💰 Price: {base_price:.2f} {PRICE_CURRENCY}"
            )
            # Displays calories, protein, base price with Markdown.
            
            # Rating form
            with st.form(key=f"form_{rid}"):
                # Creates form for submitting recipe rating.
                
                rating = st.slider("🧑‍🏫 Your rating", 1.0, 5.0, 4.0, 0.5, key=f"rate_{rid}")
                # Slider for rating (1.0-5.0, default 4.0, step 0.5).
                
                dyn_price = calculate_price(base_price, rating)
                # Calculates dynamic price based on rating.
                
                st.markdown(f"💰 Price after rating: {dyn_price:.2f} {PRICE_CURRENCY}")
                # Displays adjusted price based on rating.
                
                if st.form_submit_button("✅ Save rating"):
                    st.session_state.recipe_ratings.setdefault(
                        rid,
                        {
                            "title": rec["title"],
                            "image": rec["image"],
                            "calories": kcal,
                            "base_price": base_price,
                            "protein": macros.get("Protein", 0),
                            "fat": macros.get("Fat", 0),
                            "carbs": macros.get("Carbohydrates", 0),
                            "ratings": [],
                        },
                    )["ratings"].append(rating)
                    # Saves rating to session state, initializes entry if new.
                    # Data Flow: Rating added to ratings list for pricing/visualizations.
                    
                    st.success("Rating saved!")
                    # Shows success message after saving rating.
            
            # Cooking instructions expander
            with st.expander("👩‍🍳 Show cooking instructions"):
                render_instructions(rec)
            # Expandable section for recipe cooking instructions.
            
            st.markdown("---")
            # Horizontal line to separate recipes in UI.

# Dish of the day -------------------------------------------------------------
score_df = build_score_df()
# Builds DataFrame with composite scores for rated recipes.

best, best_score = choose_dish_of_the_day(score_df)
# Selects recipe with highest score as "Dish of the Day".

if best:
    st.header("🌟 Dish of the Day")
    # Header for "Dish of the Day" section.
    
    st.subheader(best["title"])
    # Displays top recipe title.
    
    st.image(best["image"], width=350)
    # Displays recipe image, 350px wide.
    
    st.markdown(
        f"**Composite Score:** {best_score:.2%}\n\n"
        f"⭐ Bayes rating: {best['bayes_rating']:.2f} / 5\n"
        f"💰 Price (after rating): {best['price']:.2f} {PRICE_CURRENCY}\n"
        f"🔥 Calories: {best['calories']:.0f} kcal"
    )
    # Displays composite score, Bayesian rating, price, calories.

# Score chart -----------------------------------------------------------------
if not score_df.empty:
    st.subheader("📊 Rated dishes – composite score")
    # Subheader for composite score visualization.
    
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
    # Altair bar chart for composite scores, top dish in gold.
    
    st.altair_chart(chart, use_container_width=True)
    # Renders chart, scaling to container width.

# ------------------------------------------------
# ------------------------------------------------
# 🚀 Visualisierungen
# ------------------------------------------------
# ------------------------------------------------
# Section defines visualizations for meal preferences and overview table.

if st.session_state.recipe_ratings:
    records = []
    # Initializes list for visualization DataFrame data.
    
    for rid, entry in st.session_state.recipe_ratings.items():
        # Iterates over rated recipes in session state.
        
        ratings = entry.get("ratings", [])
        # Retrieves recipe ratings list.
        
        for r in ratings:
            # Iterates over ratings for DataFrame records.
            
            records.append({
                "title": entry.get("title", f"Dish {rid}"),
                "rating": r,
                "price": entry.get("base_price", 0),
                "calories": entry.get("calories", 0),
                "protein": entry.get("protein", 0),
            })
            # Creates dictionary with recipe details per rating, adds to records.
    
    df = pd.DataFrame(records)
    # Converts records list to Pandas DataFrame.
    
    df["meal_number"] = range(1, len(df) + 1)
    # Adds sequential meal number column for plotting.
    
    def normalize_to_1_5(series, min_val, max_val):
        # Function Overview: Scales series to 1-5 range for visualization.
        # Normalizes price, calories, protein to match rating scale.
        # Data Flow: Takes series, min/max, scales to 1-5, returns scaled series.
        # Project Role: Creates comparable scales for preferences visualization.
        # Parameter: series - Pandas Series to scale.
        # Parameter: min_val - Minimum value for scaling.
        # Parameter: max_val - Maximum value for scaling.
        
        scaled = 1 + 4 * ((series - min_val) / (max_val - min_val))
        # Scales series to 1-5 using linear interpolation.
        
        return scaled.clip(1, 5)
        # Clips values to stay within 1-5 range.
    
    price_min = df["price"].min() - 0.5
    # Calculates minimum price for scaling, subtracts 0.5 for padding.
    
    price_max = df["price"].max() + 0.5
    # Calculates maximum price for scaling, adds 0.5 for padding.
    
    df["price_scaled"] = normalize_to_1_5(df["price"], price_min, price_max)
    # Scales price column to 1-5 range.
    
    df["calories_scaled"] = normalize_to_1_5(df["calories"], 100, 1500)
    # Scales calories to 1-5, assuming 100-1500 kcal range.
    
    df["protein_scaled"] = normalize_to_1_5(df["protein"], 0, 100)
    # Scales protein to 1-5, assuming 0-100g range.
    
    df["rating_scaled"] = df["rating"]
    # Uses raw rating as scaled rating (already 1-5).
    
    df_long = pd.melt(
        df,
        id_vars=["meal_number", "title"],
        value_vars=["rating_scaled", "price_scaled", "calories_scaled", "protein_scaled"],
        var_name="metric",
        value_name="value"
    )
    # Converts DataFrame to long format for multi-metric plotting.
    
    metric_labels = {
        "rating_scaled": "⭐ Rating",
        "price_scaled": "💰 Price",
        "calories_scaled": "🔥 Calories",
        "protein_scaled": "💪 Protein (g)",
    }
    # Defines display labels for chart legend metrics.
    
    df_long["metric_label"] = df_long["metric"].map(metric_labels)
    # Maps metric names to display labels for chart.
    
    st.subheader("📈 Your Meal Preferences Over Time")
    # Subheader for preferences visualization.
    
    chart = (
        alt.Chart(df_long)
        .mark_line(point=True)
        .encode(
            x=alt.X(
                "meal_number:O",
                title="Meal Number",
                axis=alt.Axis(labelAngle=0, labelFontSize=11, titleFontSize=13)
            ),
            y=alt.Y("value:Q", title="Scaled Value (1–5)", scale=alt.Scale(domain=[1, 5])),
            color=alt.Color("metric_label:N", title="Metric"),
            tooltip=[
                alt.Tooltip("title:N", title="Meal Name"),
                alt.Tooltip("metric_label:N", title="Metric"),
                alt.Tooltip("value:Q", title="Scaled", format=".2f"),
            ]
        )
        .properties(height=290)
        .interactive()
    )
    # Altair line chart for scaled metrics over meal numbers, with tooltips.
    
    st.altair_chart(chart, use_container_width=True)
    # Renders chart, scaling to container width.
    
    st.markdown("""
    <small>
    <b>ℹ️ Scale Reference:</b><br>
    🥩 <b>Protein (g):</b> 1 = 0g, 2 = 25g, 3 = 50g, 4 = 75g, 5 = 100g<br>
    🔥 <b>Calories:</b> 1 = 100 kcal, 2 = 450 kcal, 3 = 800 kcal, 4 = 1150 kcal, 5 = 1500 kcal
    </small>
    """, unsafe_allow_html=True)
    # Shows scale reference for protein/calories to clarify visualization.
    
    st.markdown("---")
    # Horizontal line separating chart from table.
    
    st.markdown("**📋 Meal Overview**")
    # Bold header for meal overview table.
    
    table = (
        df[["meal_number", "title", "rating", "calories", "protein", "price"]]
        .rename(columns={
            "meal_number": "Meal Number",
            "title": "Meal Name",
            "rating": "Rating",
            "calories": "Calories",
            "protein": "Protein",
            "price": "Price"
        })
        .set_index("Meal Number")
    )
    # Creates table from DataFrame, renames columns, sets meal number as index.
    
    st.dataframe(table, use_container_width=True)
    # Renders table, scaling to container width.
else:
    st.info("You haven't saved any ratings yet.")
    # Info message if no ratings for visualization.

# ------------------------------------------------
# ------------------------------------------------
# 🚀 Visualisierungen 2
# ------------------------------------------------
# ------------------------------------------------
# Section defines macronutrient breakdown visualization.

if st.session_state.recipe_ratings:
    records = []
    # Initializes list for macronutrient visualization data.
    
    for rid, entry in st.session_state.recipe_ratings.items():
        # Iterates over rated recipes in session state.
        
        ratings = entry.get("ratings", [])
        # Retrieves recipe ratings list.
        
        avg_rating = sum(ratings) / len(ratings) if ratings else 0
        # Calculates average rating, default 0 if no ratings.
        
        records.append({
            "title": entry.get("title", f"Dish {rid}"),
            "calories": entry.get("calories", 0),
            "protein_g": entry.get("protein", 0),
            "fat_g": entry.get("fat", 0),
            "carbs_g": entry.get("carbs", 0),
            "rating": avg_rating,
        })
        # Creates dictionary with recipe details/average rating, adds to records.
    
    df = pd.DataFrame(records)
    # Converts records list to Pandas DataFrame.
    
    df["short_title"] = df["title"].apply(lambda x: x[:25] + "..." if len(x) > 25 else x)
    # Shortens title column for x-axis readability.
    
    df["protein_kcal"] = df["protein_g"] * 4
    # Converts protein grams to kcal (4 kcal/g).
    
    df["carbs_kcal"] = df["carbs_g"] * 4
    # Converts carbs grams to kcal (4 kcal/g).
    
    df["fat_kcal"] = df["fat_g"] * 9
    # Converts fat grams to kcal (9 kcal/g).
    
    df["sum_kcal_macro"] = df[["protein_kcal", "carbs_kcal", "fat_kcal"]].sum(axis=1)
    # Calculates total kcal from macronutrients for percentages.
    
    df_long = pd.melt(
        df,
        id_vars=["short_title", "rating", "calories", "sum_kcal_macro"],
        value_vars=["protein_kcal", "carbs_kcal", "fat_kcal"],
        var_name="macro",
        value_name="kcal"
    )
    # Converts DataFrame to long format for stacked bar chart.
    
    macro_labels = {
        "protein_kcal": "💪 Protein",
        "carbs_kcal": "🍞 Carbs",
        "fat_kcal": "🧈 Fat"
    }
    # Defines display labels for macronutrients in legend.
    
    macro_colors = {
        "💪 Protein": "#1f77b4",  # Blue
        "🍞 Carbs": "#e0c97f",    # Sandy yellow
        "🧈 Fat": "#d62728",      # Red
    }
    # Defines custom colors for macronutrients in chart.
    
    df_long["macro_label"] = df_long["macro"].map(macro_labels)
    # Maps macronutrient names to display labels.
    
    df_long["percentage"] = 100 * df_long["kcal"] / df_long["sum_kcal_macro"]
    # Calculates percentage of each macronutrient to total kcal.
    
    st.subheader("🍽️ Macronutrient Breakdown per Dish")
    # Subheader for macronutrient visualization.
    
    chart = (
        alt.Chart(df_long)
        .mark_bar()
        .encode(
            x=alt.X(
                "short_title:N",
                sort="-y",
                title="Meals (sorted by your rating – highest to lowest)",
                axis=alt.Axis(
                    labelAngle=50,
                    labelFontSize=10,
                    labelLimit=160,
                    labelOverlap=False
                )
            ),
            y=alt.Y("kcal:Q", title="Calories from Macronutrients (kcal)"),
            color=alt.Color("macro_label:N", title="Macronutrient",
                scale=alt.Scale(
                    domain=list(macro_colors.keys()),
                    range=list(macro_colors.values())
                )
            ),
            order=alt.Order("macro_label", sort="ascending"),
            tooltip=[
                alt.Tooltip("short_title:N", title="Meal"),
                alt.Tooltip("macro_label:N", title="Macro"),
                alt.Tooltip("kcal:Q", title="kcal", format=".0f"),
                alt.Tooltip("percentage:Q", title="Percent", format=".1f"),
            ]
        )
        .properties(height=400)
    )
    # Altair stacked bar chart for macronutrient kcal per dish.
    
    st.altair_chart(chart, use_container_width=True)
    # Renders chart, scaling to container width.
else:
    st.info("You haven't saved any ratings yet.")
    # Info message if no ratings for macronutrient visualization.
