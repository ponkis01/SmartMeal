import requests

API_KEY = "37b9d6cf14e549739544c7a1eb1ca971"

def search_meal(query):
    url = f"https://api.spoonacular.com/recipes/complexSearch"
    params = {
        "query": query,
        "number": 5,
        "addRecipeInformation": True,
        "apiKey": API_KEY
    }
    response = requests.get(url, params=params)
    return response.json().get("results", [])


def berechne_preis(basispreis, bewertung):
    """Passt den Preis dynamisch basierend auf Bewertung an."""
    if bewertung >= 4.5:
        return round(basispreis * 1.2, 2)
    elif bewertung < 3.0:
        return round(basispreis * 0.9, 2)
    else:
        return round(basispreis, 2)


def aktualisiere_bewertung(gericht, neue_bewertung):
    """Aktualisiert den Bewertungsdurchschnitt eines Gerichts."""
    gericht["bewertungen"].append(neue_bewertung)
    durchschnitt = sum(gericht["bewertungen"]) / len(gericht["bewertungen"])
    gericht["bewertung"] = round(durchschnitt, 2)
    return gericht

import requests

url = "https://api.spoonacular.com/recipes/complexSearch"
params = {
    "apiKey": "37b9d6cf14e549739544c7a1eb1ca971",
    "minProtein": 25,
    "maxCalories": 500,
    "number": 5,
    "addRecipeNutrition": True  # wichtig!
}

response = requests.get(url, params=params)
data = response.json()

for r in data["results"]:
    print(f"{r['title']}: {r['nutrition']['nutrients']}")

recipe_id = 12345
url = f"https://api.spoonacular.com/recipes/{recipe_id}/information"
params = {"apiKey": "37b9d6cf14e549739544c7a1eb1ca971", "includeNutrition": True}
data = requests.get(url, params=params).json()

print(data["title"])
print("Protein:", [n for n in data["nutrition"]["nutrients"] if n["name"] == "Protein"][0]["amount"])
print("Zubereitung:", data["instructions"])


import requests

API_KEY = "37b9d6cf14e549739544c7a1eb1ca971"

# 1. Suche mit Proteinfilter
search_url = "https://api.spoonacular.com/recipes/complexSearch"
params = {
    "apiKey": API_KEY,
    "minProtein": 25,
    "number": 3,
    "addRecipeInformation": False
}
response = requests.get(search_url, params=params).json()
rezepte = response.get("results", [])

# 2. Hole Details pro Rezept
for rezept in rezepte:
    rezept_id = rezept["id"]
    details_url = f"https://api.spoonacular.com/recipes/{rezept_id}/information"
    details_params = {
        "apiKey": API_KEY,
        "includeNutrition": True
    }
    detail = requests.get(details_url, params=details_params).json()

    print("🍽️", detail["title"])
    print("Kalorien:", [n["amount"] for n in detail["nutrition"]["nutrients"] if n["name"] == "Calories"][0])
    print("Protein:", [n["amount"] for n in detail["nutrition"]["nutrients"] if n["name"] == "Protein"][0])
    print("Fett:", [n["amount"] for n in detail["nutrition"]["nutrients"] if n["name"] == "Fat"][0])
    print("----------")

import streamlit as st

st.set_page_config(page_title="SmartMeal 🍽️", layout="centered")

st.title("SmartMeal 🍽️ – Makrobewusste Rezeptsuche")

# 🥩 Makro-Filter
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

            # Makros extrahieren
            makros = {n["name"]: n["amount"] for n in rezept["nutrition"]["nutrients"]}
            kcal = makros.get("Calories", 0)
            protein = makros.get("Protein", 0)
            fett = makros.get("Fat", 0)
            carbs = makros.get("Carbohydrates", 0)

            st.markdown(f"🧪 **Kalorien:** {kcal:.0f} kcal")
            st.markdown(f"💪 **Protein:** {protein:.1f} g")
            st.markdown(f"🧈 **Fett:** {fett:.1f} g")
            st.markdown(f"🥖 **Kohlenhydrate:** {carbs:.1f} g")

            bewertung = st.slider(f"🧑‍🍳 Deine Bewertung für {rezept['title']}", 1.0, 5.0, 4.0, 0.5)
            neuer_preis = berechne_preis(10, bewertung)
            st.markdown(f"💰 **Preis nach Bewertung:** {neuer_preis:.2f} CHF")

            if st.button(f"✅ Bewertung speichern für {rezept['title']}"):
                st.success("Bewertung gespeichert!")