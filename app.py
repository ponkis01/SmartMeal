import requests
import streamlit as st

# ------------------------
# 🔐 Spoonacular API Key
# ------------------------
API_KEY = "37b9d6cf14e549739544c7a1eb1ca971"

# ------------------------
# 🔍 Gerichtssuche mit Query
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
# 📊 Rezepte nach Protein + Kalorien filtern
# ------------------------
def suche_rezepte_mit_protein(min_protein=25, max_calories=None, anzahl=5):
    search_url = "https://api.spoonacular.com/recipes/complexSearch"
    params = {
        "apiKey": API_KEY,
        "minProtein": min_protein,
        "number": anzahl,
        "addRecipeInformation": False
    }
    if max_calories:
        params["maxCalories"] = max_calories

    response = requests.get(search_url, params=params).json()
    results = []
    for rezept in response.get("results", []):
        r_id = rezept["id"]
        details = requests.get(
            f"https://api.spoonacular.com/recipes/{r_id}/information",
            params={"apiKey": API_KEY, "includeNutrition": True}
        ).json()
        results.append(details)
    return results

# ------------------------
# 💰 Dynamische Preislogik
# ------------------------
def berechne_preis(basispreis, bewertung):
    if bewertung >= 4.5:
        return round(basispreis * 1.2, 2)
    elif bewertung < 3.0:
        return round(basispreis * 0.9, 2)
    else:
        return round(basispreis, 2)

# ------------------------
# 🧠 Bewertung aktualisieren
# ------------------------
def aktualisiere_bewertung(gericht, neue_bewertung):
    gericht["bewertungen"].append(neue_bewertung)
    durchschnitt = sum(gericht["bewertungen"]) / len(gericht["bewertungen"])
    gericht["bewertung"] = round(durchschnitt, 2)
    return gericht

# ------------------------
# 🚀 Streamlit App
# ------------------------
st.set_page_config(page_title="SmartMeal 🍽️", layout="centered")
st.title("SmartMeal 🍽️ – Makrobewusste Rezeptsuche")

# 🥩 Makro-Filter Sidebar
st.sidebar.header("Makro-Filter")
min_protein = st.sidebar.slider("Mind. Protein (g)", 0, 100, 25)
max_calories = st.sidebar.slider("Max. Kalorien", 100, 1500, 600)
anzahl = st.sidebar.slider("Anzahl Gerichte", 1, 10, 3)

# 🔍 Suche auslösen
if st.button("🔍 Gerichte mit Filter suchen"):
    rezepte = suche_rezepte_mit_protein(min_protein, max_calories, anzahl)

    if not rezepte:
        st.warning("Keine passenden Gerichte gefunden.")
    else:
        for rezept in rezepte:
            st.subheader(rezept["title"])
            st.image(rezept["image"], width=300)

            makros = {n["name"]: n["amount"] for n in rezept["nutrition"]["nutrients"]}
            kcal = makros.get("Calories", 0)
            protein = makros.get("Protein", 0)
            fett = makros.get("Fat", 0)
            carbs = makros.get("Carbohydrates", 0)

            st.markdown(f"🧪 **Kalorien:** {kcal:.0f} kcal")
            st.markdown(f"💪 **Protein:** {protein:.1f} g")
            st.markdown(f"🥈 **Fett:** {fett:.1f} g")
            st.markdown(f"🥖 **Kohlenhydrate:** {carbs:.1f} g")

            bewertung = st.slider(f"🧑‍🏫 Deine Bewertung für {rezept['title']}", 1.0, 5.0, 4.0, 0.5)
            neuer_preis = berechne_preis(10, bewertung)
            st.markdown(f"💰 **Preis nach Bewertung:** {neuer_preis:.2f} CHF")

            if st.button(f"✅ Bewertung speichern für {rezept['title']}"):
                st.success("Bewertung gespeichert!")
