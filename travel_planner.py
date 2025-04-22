import os
import tkinter as tk
from tkinter import messagebox, font, scrolledtext
from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.prompts import ChatPromptTemplate, HumanMessagePromptTemplate
from langchain.schema import SystemMessage
from langchain.chains import LLMChain
from markdown import markdown
from tkinterweb import HtmlFrame
import json

load_dotenv()

llm = ChatGoogleGenerativeAI(model="gemini-2.0-flash", temperature=0.7)


class ConversationPlanner:
    def __init__(self, root):
        self.root = root
        self.conversation_history = []
        self.preferences = {
            "destination": None,
            "dates": None,
            "cuisines": None,
            "dietary_restrictions": None,
            "budget": None,
            "experience": None
        }
        self.fields = list(self.preferences.keys())
        self.setup_ui()
        self.add_to_conversation(
            "Planner",
            "Hi there! Tell me about your upcoming food trip. "
            "Mention anything you want — where you're going, what you want to eat, "
            "when you're going, dietary needs, budget, and vibe. I'll help plan it!"
        )

    def setup_ui(self):
        self.root.title("🍽️ Conversational Food Planner")
        self.root.geometry("900x900")
        self.root.configure(bg="#ffffff")

        # Fonts
        self.heading_font = ("Helvetica", 18, "bold")
        self.label_font = ("Helvetica", 12)

        # Header
        header = tk.Label(
            self.root,
            text="🍽️ Conversational Food Itinerary Planner",
            font=self.heading_font,
            bg="#ffffff",
            fg="#333"
        )
        header.pack(pady=(20, 10))

        # Conversation Frame
        self.conversation_frame = tk.Frame(self.root, bg="#ffffff")
        self.conversation_frame.pack(pady=10, padx=20, fill=tk.BOTH, expand=True)

        self.conversation_text = scrolledtext.ScrolledText(
            self.conversation_frame,
            wrap=tk.WORD,
            font=self.label_font,
            bg="#f9f9f9",
            fg="#222",
            padx=12,
            pady=12,
            bd=0,
            relief=tk.FLAT,
            highlightthickness=1,
            highlightbackground="#ddd"
        )
        self.conversation_text.pack(fill=tk.BOTH, expand=True)
        self.conversation_text.config(state=tk.DISABLED)

        # Input Frame
        self.input_frame = tk.Frame(self.root, bg="#ffffff")
        self.input_frame.pack(pady=15, padx=20, fill=tk.X)

        self.user_input = tk.Entry(
            self.input_frame,
            font=self.label_font,
            width=70,
            bg="#ffffff",
            fg="#333",
            relief=tk.FLAT,
            highlightthickness=1,
            highlightbackground="#ccc",
            insertbackground="#333"
        )
        self.user_input.pack(side=tk.LEFT, padx=(0, 10), ipady=6)
        self.user_input.bind("<Return>", lambda event: self.process_answer())

        self.submit_btn = tk.Button(
            self.input_frame,
            text="Send",
            command=self.process_answer,
            bg="#007acc",
            fg="white",
            activebackground="#005b99",
            activeforeground="white",
            font=self.label_font,
            padx=16,
            pady=6,
            relief=tk.FLAT,
            cursor="hand2"
        )
        self.submit_btn.pack(side=tk.LEFT)

        # Output (HTML itinerary) display
        self.output_frame = HtmlFrame(self.root, horizontal_scrollbar="auto")
        self.output_frame.pack(padx=20, pady=(0, 20), fill=tk.BOTH, expand=True)
        self.output_frame.load_html("""
            <div style='font-family:Helvetica, sans-serif; color:#666; font-style:italic; padding:1em;'>
                Your itinerary will appear here after the conversation...
            </div>
        """)

    def add_to_conversation(self, sender, message):
        self.conversation_text.config(state=tk.NORMAL)
        self.conversation_text.insert(tk.END, f"{sender}: {message}\n\n")
        self.conversation_text.config(state=tk.DISABLED)
        self.conversation_text.see(tk.END)

    def process_answer(self):
        user_input = self.user_input.get().strip()
        if not user_input:
            return

        self.add_to_conversation("You", user_input)
        self.user_input.delete(0, tk.END)

        if not any(self.preferences.values()):
            extracted = self.extract_preferences(user_input)
            for key in self.fields:
                if extracted.get(key):
                    self.preferences[key] = extracted[key]
        else:
            missing_field = self.get_next_missing_field()
            if missing_field:
                self.preferences[missing_field] = user_input

        next_missing = self.get_next_missing_field()
        if next_missing:
            followup = self.generate_followup_question(next_missing)
            self.add_to_conversation("Planner", followup)
        else:
            self.generate_itinerary()

    def get_next_missing_field(self):
        for key in self.fields:
            if not self.preferences[key]:
                return key
        return None

    def generate_followup_question(self, field):
        field_questions = {
            "destination": "Where will you be traveling to?",
            "dates": "When will your trip take place? Please use MM/DD/YYYY - MM/DD/YYYY format.",
            "cuisines": "What cuisines are you interested in?",
            "dietary_restrictions": "Any dietary restrictions I should keep in mind?",
            "budget": "What's your budget level? (Budget-friendly, Moderate, High-end, Luxury)",
            "experience": "What kind of dining experience are you looking for? (Casual, Fine Dining, Family-friendly, etc.)"
        }
        return field_questions.get(field, "Can you tell me more?")

    def extract_preferences(self, user_input):
        extraction_prompt = ChatPromptTemplate.from_messages([
            SystemMessage(content="""You are an AI assistant that extracts travel preferences from user messages.

            Given a message from a user, extract the following fields if they are mentioned:
            - Destination
            - Dates (in MM/DD/YYYY - MM/DD/YYYY format)
            - Cuisines (list them)
            - Dietary Restrictions
            - Budget
            - Dining Vibe

            Return your answer as a JSON object with keys:
            'destination', 'dates', 'cuisines', 'dietary_restrictions', 'budget', 'experience'.

            If a field is missing, set its value to null.
            """),
            HumanMessagePromptTemplate.from_template("{user_input}")
        ])

        extraction_chain = LLMChain(llm=llm, prompt=extraction_prompt)
        response = extraction_chain.run(user_input=user_input)
        try:
            return json.loads(response)
        except Exception:
            try:
                return eval(response)  # fallback if LLM returns python-style dict
            except Exception as e:
                messagebox.showerror("Extraction Error", f"Couldn't parse response:\n{response}")
                return {}

    def generate_itinerary(self):
        try:
            self.output_frame.load_html(
                "<p style='color:#666;font-style:italic'>Generating your itinerary... Please wait...</p>")
            self.root.update()

            validation_error = self.validate_inputs()
            if validation_error:
                messagebox.showerror("Validation Error", validation_error)
                return

            prompt_template = ChatPromptTemplate.from_messages([
                SystemMessage(
                    content="You are a food-savvy AI travel planner. Generate a restaurant itinerary in Markdown format."),
                HumanMessagePromptTemplate.from_template("""\
# {destination} Food Itinerary: {dates}
**Cuisines:** {cuisines}  
**Dietary Restrictions:** {dietary_restrictions}  
**Budget:** {budget}  
**Dining Vibe:** {experience}

Generate a daily restaurant plan in **Markdown format** with:
- Headings for each date
- Subheadings for each meal (Brunch, Lunch, Dinner, etc.)
- Each restaurant on its own line
- Include name, cuisine type, budget range, and a short 1-sentence description
- Do not include any emojis
- Use horizontal rules (---) between days

Ensure the final output is valid and clean Markdown.""")
            ])

            itinerary_chain = LLMChain(llm=llm, prompt=prompt_template)
            itinerary = itinerary_chain.run(**self.preferences)

            html_result = markdown(itinerary)
            self.output_frame.load_html(html_result)
            self.add_to_conversation("Planner", "Here's your personalized food itinerary! Enjoy your trip!")

        except Exception as e:
            messagebox.showerror("Error", f"Something went wrong:\n{str(e)}")

    def validate_inputs(self):
        validation_prompt = ChatPromptTemplate.from_messages([
            SystemMessage(content="""You are an input validation assistant. Analyze these travel planner inputs and:
            1. Check if required fields are empty
            2. Validate date format (should be like 'MM/DD/YYYY - MM/DD/YYYY' or similar)
            3. Check cuisine list has valid entries
            4. Return ONLY the validation errors, or 'OK' if all valid"""),
            HumanMessagePromptTemplate.from_template("""\
Destination: {destination}
Dates: {dates}
Cuisines: {cuisines}
Dietary Restrictions: {dietary_restrictions}
Budget: {budget}
Dining Vibe: {experience}
""")
        ])

        validation_chain = LLMChain(llm=llm, prompt=validation_prompt)
        validation_result = validation_chain.run(**self.preferences)

        return validation_result if validation_result != "OK" else None


# Main app
root = tk.Tk()
app = ConversationPlanner(root)
root.mainloop()
