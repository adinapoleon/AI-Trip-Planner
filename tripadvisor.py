import tkinter as tk
from tkinter import ttk
import webbrowser
import requests
import os
import json
import re
from pathlib import Path
from dotenv import load_dotenv
from urllib.parse import quote

load_dotenv()

# Custom style configuration
def configure_styles():
    style = ttk.Style()
    style.theme_use('clam')

    # Color scheme and font updates
    style.configure('TFrame', background="#ffffff")
    style.configure('TLabel', background="#ffffff", font=('Segoe UI', 11))
    style.configure('Header.TLabel', background="#ffffff", font=('Segoe UI', 18, 'bold'), foreground="#0077b6")
    style.configure('Restaurant.TLabel', font=('Segoe UI', 13, 'bold'), foreground="#028c76")
    style.configure('Address.TLabel', font=('Segoe UI', 10))
    style.configure('Review.TLabel', font=('Segoe UI', 10), wraplength=600, justify='left')
    style.configure('Link.TLabel', font=('Segoe UI', 11, 'underline'), foreground='#0077b6', cursor='hand2')
    style.configure('TButton', font=('Segoe UI', 11), padding=6)


def extract_places(data):
    """Process raw JSON data according to extraction rules"""
    extracted = []
    for i, place in enumerate(data):
        # Ignore first item
        if i == 0:
            continue

        name = place["name"]

        if name.startswith("#") or name.startswith("Lunch") or name.startswith("Dinner"):
            extracted.append({
                "name": name.split(": ", 1)[1].strip(),
                "address": place["address"],
                "maps_link": place["maps_link"]
            })

        elif name.startswith("Day"):
            if len(name) > 30:
                # Split by either " - " or " : " and take the second part
                split_parts = name.split(" - ", 1) if " - " in name else name.split(": ", 1)
                extracted.append({
                    "name": split_parts[1].strip() if len(split_parts) > 1 else name,  # Fallback to original if split fails
                    "address": place["address"],
                    "maps_link": place["maps_link"]
                })
            else:
                continue

        else:
            extracted.append({
                "name": name,
                "address": place["address"],
                "maps_link": place["maps_link"]
            })

    return extracted


def load_restaurants():
    json_path = Path(__file__).parent / "restaurants.json"
    try:
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            return extract_places(data)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"Error loading restaurants.json: {e}")
        return []


places = load_restaurants()
API_KEY = os.getenv("TRIP_ADVISOR_API_KEY")


class RestaurantReviewApp:
    def __init__(self, root):
        self.root = root
        self.setup_ui()
        configure_styles()

    def setup_ui(self):
        self.root.title("🍽️ Restaurant Reviews")
        self.root.geometry("800x700+100+300")
        self.root.configure(bg="#ffffff")
        self.root.minsize(800, 600)

        header_frame = ttk.Frame(self.root)
        header_frame.pack(fill=tk.X, padx=20, pady=(15, 10))

        ttk.Label(
            header_frame,
            text="Houston Food Itinerary: May 18th - May 21st",
            style='Header.TLabel'
        ).pack(side=tk.LEFT)

        main_frame = ttk.Frame(self.root)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=5)

        canvas = tk.Canvas(main_frame, bg="#ffffff", highlightthickness=0)
        scrollbar = ttk.Scrollbar(main_frame, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)

        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        for place in places:
            self.create_restaurant_card(scrollable_frame, place)

    def create_restaurant_card(self, parent, place):
        card_frame = ttk.Frame(parent, relief=tk.RIDGE, borderwidth=1, padding=15)
        card_frame.pack(fill=tk.X, pady=10, padx=5, expand=True)

        name_label = ttk.Label(
            card_frame,
            text=place["name"],
            style='Restaurant.TLabel'
        )
        name_label.pack(anchor="w", fill=tk.X)
        name_label.bind("<Button-1>", lambda e: webbrowser.open(place["maps_link"]))

        ttk.Label(
            card_frame,
            text=f"📍 {place['address']}",
            style='Address.TLabel'
        ).pack(anchor="w", pady=(5, 0), fill=tk.X)

        reviews = self.get_reviews(place["name"], place["address"])
        if reviews:
            review_frame = ttk.Frame(card_frame)
            review_frame.pack(fill=tk.X, pady=(10, 0), expand=True)

            ttk.Label(
                review_frame,
                text="Top Reviews:",
                style='Restaurant.TLabel'
            ).pack(anchor="w", fill=tk.X)

            for review in reviews:
                ttk.Label(
                    review_frame,
                    text=review,
                    style='Review.TLabel'
                ).pack(anchor="w", padx=10, pady=2, fill=tk.X)
        else:
            ttk.Label(
                card_frame,
                text="No reviews found",
                style='Address.TLabel',
                foreground='gray'
            ).pack(anchor="w", pady=(10, 0), fill=tk.X)

    def get_location_id(self, name, address):
        if not API_KEY:
            return None

        def try_search(query, address=None):
            search_query = quote(query.lower())
            url = (f"https://api.content.tripadvisor.com/api/v1/location/search"
                   f"?key={API_KEY}"
                   f"&searchQuery={search_query}"
                   f"&category=restaurant"
                   f"&language=en")

            if address:
                url += f"&address={quote(address)}"

            try:
                response = requests.get(url, timeout=10)
                response.raise_for_status()
                data = response.json()
                if data and "data" in data and len(data["data"]) > 0:
                    return data["data"][0]["location_id"]
            except (requests.RequestException, ValueError, KeyError) as e:
                print(f"Search error: {e}")
            return None

        location_id = try_search(name, address)
        if not location_id:
            print(f"No results with address, trying without address for {name}...")
            location_id = try_search(name)

        return location_id

    def get_reviews(self, name, address):
        if not API_KEY:
            return []

        location_id = self.get_location_id(name, address)
        if not location_id:
            return []

        url = (f"https://api.content.tripadvisor.com/api/v1/location/{location_id}/reviews"
               f"?key={API_KEY}&language=en")

        try:
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            data = response.json()
            reviews = []

            if "data" in data:
                for review in data["data"][:3]:
                    text = review.get("text", "").strip()
                    if text:
                        rating = review.get("rating", "?")
                        reviews.append(f"⭐ {rating}/5 - {text}")
            return reviews
        except (requests.RequestException, ValueError, KeyError) as e:
            print(f"Error fetching reviews for location {location_id}: {e}")
            return []


if __name__ == "__main__":
    root = tk.Tk()
    app = RestaurantReviewApp(root)
    root.mainloop()
