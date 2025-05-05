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

def clean_address(address):
    """Remove parentheses and their contents from addresses"""
    return re.sub(r'\([^)]*\)', '', address).strip()

def extract_places(data):
    """Process raw JSON data according to extraction rules"""
    extracted = []
    for i, place in enumerate(data):
        # Ignore first item
        if i == 0:
            continue

        name = place["name"]

        if name.startswith("#"):
            extracted.append({
                "name": name.split(": ", 1)[1].strip(),
                "address": place["address"],
                "maps_link": place["maps_link"]
            })

        elif name.startswith("Day") and " - " in name:
            extracted.append({
                "name": name.split(" - ", 1)[1].strip(),
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


def get_location_id(name, address):
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
            address_query = quote(address)
            url += f"&address={address_query}"

        try:
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            data = response.json()

            if data and "data" in data and len(data["data"]) > 0:
                return data["data"][0]["location_id"]
        except (requests.RequestException, ValueError, KeyError) as e:
            print(f"Search error: {e}")
        return None

    # First try with both name and address
    location_id = try_search(name, address)

    # If not found, try with just the name
    if not location_id:
        print(f"No results with address, trying without address for {name}...")
        location_id = try_search(name)

    return location_id


def get_reviews(location_id):
    if not API_KEY or not location_id:
        return []

    url = (f"https://api.content.tripadvisor.com/api/v1/location/{location_id}/reviews"
           f"?key={API_KEY}"
           f"&language=en")

    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()
        reviews = []

        if "data" in data:
            for review in data["data"][:3]:  # Top 3 reviews
                text = review.get("text", "").strip()
                if text:
                    rating = review.get("rating", "?")
                    reviews.append(f"⭐ {rating}/5 - {text}")
        return reviews

    except (requests.RequestException, ValueError, KeyError) as e:
        print(f"Error fetching reviews for location {location_id}: {e}")
        return []


def open_link(url):
    webbrowser.open_new(url)


def display_reviews(root, place):
    frame = ttk.Frame(root)
    frame.pack(padx=10, pady=10, anchor="w", fill="x")

    # Hyperlinked name
    link = tk.Label(
        frame,
        text=place["name"],
        foreground="blue",
        cursor="hand2",
        font=("Arial", 12, "underline")
    )
    link.pack(anchor="w")
    link.bind("<Button-1>", lambda e: open_link(place["maps_link"]))

    # Display address
    address_label = tk.Label(frame, text=f"Address: {place['address']}")
    address_label.pack(anchor="w")

    # Fetch and display reviews
    reviews = []
    location_id = get_location_id(place["name"], place["address"])
    if location_id:
        reviews = get_reviews(location_id)

    if reviews:
        review_frame = ttk.Frame(frame)
        review_frame.pack(anchor="w", pady=(5, 0))

        tk.Label(review_frame, text="Top Reviews:", font=("Arial", 10, "bold")).pack(anchor="w")
        for review in reviews:
            tk.Label(
                review_frame,
                text=review,
                wraplength=600,
                justify="left"
            ).pack(anchor="w", padx=10)
    else:
        tk.Label(
            frame,
            text="No reviews found or API not configured.",
            fg="gray"
        ).pack(anchor="w")


def main():
    root = tk.Tk()
    root.title("TripAdvisor Food Itinerary Reviews")

    if not API_KEY:
        tk.Label(
            root,
            text="Warning: TRIP_ADVISOR_API_KEY not found in .env file",
            fg="red"
        ).pack(pady=10)

    # Create scrollable canvas
    canvas = tk.Canvas(root)
    scroll_y = ttk.Scrollbar(root, orient="vertical", command=canvas.yview)

    scroll_frame = ttk.Frame(canvas)
    canvas.create_window((0, 0), window=scroll_frame, anchor="nw")
    canvas.configure(yscrollcommand=scroll_y.set)

    # Populate reviews for all extracted places
    for place in places:
        display_reviews(scroll_frame, place)

    scroll_frame.bind(
        "<Configure>",
        lambda e: canvas.configure(scrollregion=canvas.bbox("all")))

    canvas.pack(side="left", fill="both", expand=True)
    scroll_y.pack(side="right", fill="y")

    root.mainloop()

if __name__ == "__main__":
    main()