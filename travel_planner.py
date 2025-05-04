import json
import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.prompts import ChatPromptTemplate, HumanMessagePromptTemplate
from langchain.schema import SystemMessage
from langchain.chains import LLMChain
from markdown import markdown
from tkinterweb import HtmlFrame
from datetime import datetime
import re

load_dotenv()


class StyledConversationPlanner:
    def __init__(self, root):
        self.root = root
        self.questions = [
            ("destination", "Where will you be traveling to?", "text"),
            ("dates", "What are the dates of your trip? (MM/DD/YYYY - MM/DD/YYYY)", "date"),
            ("travelers", "How many people are traveling?", "number"),
            ("cuisines", "What cuisines are you interested in? (Separate with commas)", "multiselect"),
            ("dietary_restrictions", "Any dietary restrictions or allergies?", "text"),
            ("budget", "What's your budget level?", "select", ["Budget-friendly", "Moderate", "High-end", "Luxury"]),
            ("experience", "What kind of dining experience are you looking for?", "select",
             ["Casual", "Fine Dining", "Local Favorites", "Mix of everything"]),
            ("additional_notes", "Any other preferences or special requests?", "optional")
        ]
        self.answers = {}
        self.current_question_index = 0
        self.output_window = None
        self.setup_ui()
        self.ask_next_question()
        self.itinerary_json = None
        self.last_html = None
        self.waiting_for_changes = False

        # Initialize LLM with error handling
        try:
            self.llm = ChatGoogleGenerativeAI(model="gemini-2.0-flash", temperature=0.7)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to initialize AI: {str(e)}")
            self.root.destroy()

    def setup_ui(self):
        self.root.title("🍽️ Travel Food Planner AI")
        self.root.geometry("1000x800")
        self.root.configure(bg="#f5f7fa")
        self.root.minsize(800, 600)

        # Custom style
        style = ttk.Style()
        style.theme_use('clam')
        style.configure('TButton', font=('Helvetica', 11), padding=6)
        style.configure('TFrame', background="#f5f7fa")

        # Header
        header_frame = ttk.Frame(self.root)
        header_frame.pack(fill=tk.X, padx=20, pady=(15, 5))

        self.logo = tk.Label(header_frame,
                             text="🍽️ Travel Food Planner",
                             font=("Helvetica", 18, "bold"),
                             fg="#2c3e50",
                             bg="#f5f7fa")
        self.logo.pack(side=tk.LEFT)

        # Conversation area
        self.conversation_frame = ttk.Frame(self.root)
        self.conversation_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=5)

        self.conversation_text = scrolledtext.ScrolledText(
            self.conversation_frame,
            wrap=tk.WORD,
            font=("Helvetica", 12),
            bg="white",
            padx=15,
            pady=15,
            relief=tk.FLAT
        )
        self.conversation_text.pack(fill=tk.BOTH, expand=True)
        self.conversation_text.config(state=tk.DISABLED)

        # Input area
        self.input_frame = ttk.Frame(self.root)
        self.input_frame.pack(fill=tk.X, padx=20, pady=(5, 15))

        self.user_input = tk.Text(
            self.input_frame,
            height=3,
            font=("Helvetica", 12),
            bg="white",
            relief=tk.SOLID,
            borderwidth=1,
            padx=10,
            pady=10
        )
        self.user_input.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 10))
        self.user_input.bind("<Return>", self.on_enter)
        self.user_input.bind("<Shift-Return>", lambda e: self.user_input.insert(tk.INSERT, "\n"))

        submit_btn = ttk.Button(
            self.input_frame,
            text="Send",
            command=self.process_input,
            style='TButton'
        )
        submit_btn.pack(side=tk.LEFT)

        # Configure tags for different message types
        self.conversation_text.tag_config("system", foreground="#3498db")
        self.conversation_text.tag_config("user", foreground="#2ecc71")
        self.conversation_text.tag_config("error", foreground="#e74c3c")
        self.conversation_text.tag_config("warning", foreground="#f39c12")

    def on_enter(self, event):
        self.process_input()
        return "break"

    def add_to_conversation(self, speaker, message, msg_type="normal"):
        self.conversation_text.config(state=tk.NORMAL)

        # Insert speaker name with appropriate color
        if speaker.lower() == "planner":
            self.conversation_text.insert(tk.END, f"Planner: ", "system")
        else:
            self.conversation_text.insert(tk.END, f"{speaker}: ", "user")

        # Insert message with appropriate formatting
        self.conversation_text.insert(tk.END, f"{message}\n\n", msg_type)

        self.conversation_text.config(state=tk.DISABLED)
        self.conversation_text.see(tk.END)

    def validate_input(self, input_text, input_type):
        if not input_text.strip():
            return False, "Please provide an answer"

        if input_type == "date":
            try:
                dates = [d.strip() for d in input_text.split("-")]
                if len(dates) != 2:
                    return False, "Please enter dates in format MM/DD/YYYY - MM/DD/YYYY"

                for date_str in dates:
                    datetime.strptime(date_str.strip(), "%m/%d/%Y")

                return True, ""
            except ValueError:
                return False, "Invalid date format. Please use MM/DD/YYYY"

        elif input_type == "number":
            if not input_text.isdigit():
                return False, "Please enter a valid number"
            return True, ""

        return True, ""

    def ask_next_question(self):
        if self.current_question_index < len(self.questions):
            current_question = self.questions[self.current_question_index]
            key, question, *question_type = current_question

            # Format the question based on type
            if len(question_type) > 1 and question_type[0] == "select":
                options = question_type[1]
                question += f" (Options: {', '.join(options)})"
            elif question_type[0] == "optional":
                question += " (Optional)"

            self.add_to_conversation("Planner", question)
            self.user_input.focus_set()
        else:
            self.generate_itinerary()

    def process_input(self):
        user_input = self.user_input.get("1.0", tk.END).strip()

        if self.waiting_for_changes:
            self.handle_itinerary_changes(user_input)
            return

        # Handle empty input for non-optional questions
        current_question = self.questions[self.current_question_index]
        key, _, input_type, *rest = current_question

        if not user_input and input_type != "optional":
            self.add_to_conversation("Planner", "Please provide an answer.", "warning")
            return

        # Validate input
        if user_input and input_type != "text":
            is_valid, error_msg = self.validate_input(user_input, input_type)
            if not is_valid:
                self.add_to_conversation("Planner", error_msg, "warning")
                return

        # Store answer if provided
        if user_input:
            self.answers[key] = user_input
            self.add_to_conversation("You", user_input)

        self.user_input.delete("1.0", tk.END)
        self.current_question_index += 1
        self.ask_next_question()

    def handle_itinerary_changes(self, user_input):
        """Process user's requested changes to the itinerary"""
        if user_input.lower() in ['no', 'n', '']:
            self.add_to_conversation("You", "No changes needed")
            self.add_to_conversation("Planner", "Great! Enjoy your trip!")
            self.waiting_for_changes = False
            return

        self.add_to_conversation("You", user_input)
        self.add_to_conversation("Planner", "Updating your itinerary with the requested changes...")

        try:
            # Create a prompt to modify the existing itinerary
            prompt_template = ChatPromptTemplate.from_messages([
                SystemMessage(content="""
                    You are an expert travel food planner that modifies existing itineraries based on user feedback.
                    Your responses should be in Markdown format with clear organization and helpful details.
                    For each restaurant, clearly include the name and address in this format:

                    ### Restaurant Name
                    - Address: Full address here
                    - Cuisine: Type of cuisine
                    - Price range: $, $$, $$$, etc.
                    - Description: Brief description
                """),
                HumanMessagePromptTemplate.from_template("""
                    Please modify the following food itinerary based on these requested changes:
                    {requested_changes}

                    Original Itinerary Details:
                    - Destination: {destination}
                    - Dates: {dates}
                    - Travelers: {travelers}
                    - Cuisines: {cuisines}
                    - Dietary restrictions: {dietary_restrictions}
                    - Budget: {budget}
                    - Experience: {experience}
                    - Additional notes: {additional_notes}

                    Here is the current itinerary (in Markdown format):
                    {current_itinerary}

                    Please:
                    1. Make the requested changes
                    2. Keep the same Markdown formatting
                    3. Explain any significant changes made
                    4. Maintain all the original information that wasn't requested to change
                """)
            ])

            chain = LLMChain(llm=self.llm, prompt=prompt_template)

            # Get the current markdown content from the HTML
            current_markdown = self.extract_markdown_from_html(self.last_html)

            markdown_result = chain.run(
                requested_changes=user_input,
                current_itinerary=current_markdown,
                **self.answers
            )

            # Extract restaurant info
            restaurants = self.extract_restaurant_info(markdown_result)
            self.itinerary_json = json.dumps({
                "destination": self.answers.get('destination', ''),
                "dates": self.answers.get('dates', ''),
                "restaurants": restaurants
            }, indent=2)

            # Process markdown to add Google Maps links
            processed_markdown = self.add_maps_links_to_markdown(markdown_result)

            # Convert to HTML and display
            html_result = self.convert_markdown_to_html(processed_markdown)
            self.output_frame.load_html(html_result)
            self.last_html = html_result

            # Ask if more changes are needed
            self.add_to_conversation("Planner",
                                     "Your itinerary has been updated. If you would like to make any changes just list them below.")
            self.user_input.delete("1.0", tk.END)

        except Exception as e:
            self.add_to_conversation("Planner", f"Sorry, I encountered an error updating your itinerary: {str(e)}",
                                     "error")
            self.waiting_for_changes = False

    def extract_markdown_from_html(self, html_content):
        """Extract the original markdown content from the HTML"""
        # This is a simplified approach - in a real app you might want to store the original markdown
        # or use a more sophisticated HTML-to-markdown converter
        try:
            # Extract content between <body> tags
            body_start = html_content.find('<body>') + 6
            body_end = html_content.find('</body>')
            body_content = html_content[body_start:body_end]

            # Remove HTML tags (simple approach)
            clean_text = re.sub('<[^<]+?>', '', body_content)
            return clean_text.strip()
        except Exception:
            return "Could not extract original content"

    def add_maps_links_to_markdown(self, markdown_text):
        """Add Google Maps links to addresses in the markdown"""
        processed_markdown = []

        def get_google_maps_link(address):
            if not address:
                return ""
            formatted_address = (
                address.replace(", ", "+")
                .replace(" ", "+")
                .replace("&", "%26")
                .replace("#", "%23")
            )
            return f"https://www.google.com/maps/search/?api=1&query={formatted_address}"

        for line in markdown_text.split('\n'):
            if line.startswith('### '):
                # This is a restaurant title line
                restaurant_name = line[4:].strip()
                processed_markdown.append(line)
            elif line.strip().startswith('- Address:'):
                # This is an address line - we'll add the link in the next step
                address = line.replace('- Address:', '').strip()
                maps_link = get_google_maps_link(address)
                if maps_link:
                    # Add the link right after the restaurant name
                    if processed_markdown and processed_markdown[-1].startswith('### '):
                        last_line = processed_markdown[-1]
                        processed_markdown[-1] = f"{last_line} [📍]({maps_link})"
                processed_markdown.append(line)
            else:
                processed_markdown.append(line)

        return '\n'.join(processed_markdown)

    def convert_markdown_to_html(self, markdown_text):
        """Convert markdown text to styled HTML"""
        return f"""
            <html>
            <head>
                <style>
                    body {{ font-family: 'Helvetica', Arial, sans-serif; line-height: 1.6; color: #333; max-width: 900px; margin: 0 auto; padding: 20px; }}
                    h1 {{ color: #2c3e50; border-bottom: 2px solid #3498db; padding-bottom: 10px; }}
                    h2 {{ color: #2980b9; }}
                    h3 {{ color: #16a085; display: flex; align-items: center; }}
                    .restaurant {{ background: #f9f9f9; padding: 15px; border-radius: 5px; margin-bottom: 15px; }}
                    .tip {{ background: #e8f4fc; padding: 10px; border-left: 4px solid #3498db; margin: 15px 0; }}
                    hr {{ border: 0; height: 1px; background: #ddd; margin: 30px 0; }}
                    a {{ color: #3498db; text-decoration: none; }}
                    a:hover {{ text-decoration: underline; }}
                    .map-link {{ margin-left: 10px; font-size: 0.8em; }}
                </style>
            </head>
            <body>
                {markdown(markdown_text)}
            </body>
            </html>
        """

    def extract_restaurant_info(self, markdown_text):
        """Extract restaurant information from markdown text and return as JSON"""
        pattern = r"###?\s*(.*?)\n.*?Address:\s*(.*?)(?:\n|$)"
        matches = re.findall(pattern, markdown_text, re.IGNORECASE | re.DOTALL)

        restaurants = []
        for name, address in matches:
            restaurants.append({
                "name": name.strip(),
                "address": address.strip()
            })

        return restaurants

    def generate_itinerary(self):
        try:
            if self.output_window is None or not self.output_window.winfo_exists():
                self.output_window = tk.Toplevel(self.root)
                self.output_window.title(f"Food Itinerary for {self.answers.get('destination', 'Your Trip')}")
                self.output_window.geometry("900x700")
                self.output_window.configure(bg="#f5f7fa")

                # Add output frame
                self.output_frame = HtmlFrame(self.output_window, horizontal_scrollbar="auto")
                self.output_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

            self.output_frame.load_html("""
                <div style='text-align:center; padding:50px; color:#666; font-style:italic'>
                    <h3>Generating your personalized food itinerary...</h3>
                    <p>This may take a moment</p>
                </div>
            """)
            self.output_window.update()

            # Generate more detailed prompt
            prompt_template = ChatPromptTemplate.from_messages([
                SystemMessage(content="""
                    You are an expert travel food planner that creates detailed, personalized restaurant itineraries.
                    Your responses should be in Markdown format with clear organization and helpful details.
                    Include practical information like reservation recommendations and travel tips.
                    For each restaurant, clearly include the name and address in this format:

                    ### Restaurant Name
                    - Address: Full address here
                    - Cuisine: Type of cuisine
                    - Price range: $, $$, $$$, etc.
                    - Description: Brief description
                """),
                HumanMessagePromptTemplate.from_template("""
                    Create a detailed food itinerary for a trip to {destination} from {dates}.

                    Travel Details:
                    - Number of travelers: {travelers}
                    - Preferred cuisines: {cuisines}
                    - Dietary restrictions: {dietary_restrictions}
                    - Budget level: {budget}
                    - Dining experience: {experience}
                    - Additional notes: {additional_notes}

                    Requirements:
                    - Organize by day with clear headings
                    - Include breakfast, lunch, and dinner options each day
                    - For each restaurant provide:
                      * Name (as ### heading)
                      * Address (clearly labeled)
                      * Cuisine type
                      * Price range
                      * Short description
                      * Why it was selected
                      * Any reservation recommendations
                    - Include local food specialties to try
                    - Add practical tips about dining culture in the area
                    - Use horizontal rules between days
                    - Format for easy reading with Markdown
                """)
            ])

            chain = LLMChain(llm=self.llm, prompt=prompt_template)

            markdown_result = chain.run(**self.answers)

            # Extract restaurant info
            restaurants = self.extract_restaurant_info(markdown_result)
            self.itinerary_json = json.dumps({
                "destination": self.answers.get('destination', ''),
                "dates": self.answers.get('dates', ''),
                "restaurants": restaurants
            }, indent=2)

            # Process markdown to add Google Maps links
            processed_markdown = self.add_maps_links_to_markdown(markdown_result)

            # Convert to HTML and display
            html_result = self.convert_markdown_to_html(processed_markdown)
            self.output_frame.load_html(html_result)
            self.last_html = html_result

            # Ask if user wants to make changes
            self.add_to_conversation("Planner",
                                     "Your personalized food itinerary is ready! Check the window for details.\n"
                                     "Would you like to make any changes to the itinerary? (yes/no)")
            self.waiting_for_changes = True

        except Exception as e:
            self.add_to_conversation("Planner", f"Sorry, I encountered an error generating your itinerary: {str(e)}",
                                     "error")


if __name__ == "__main__":
    root = tk.Tk()
    try:
        app = StyledConversationPlanner(root)
        root.mainloop()
    except Exception as e:
        messagebox.showerror("Fatal Error", f"The application encountered an error: {str(e)}")