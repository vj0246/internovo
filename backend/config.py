PEOPLE = [
    {
        "name": "Riya",
        "role": "Social Media & Marketing",
        "description": (
            "Social media creatives, marketing banners, Instagram/Facebook/LinkedIn posts, "
            "ad creatives, promotional flyers, digital marketing visuals, campaign assets."
        ),
    },
    {
        "name": "Sameer",
        "role": "Decks & Presentations",
        "description": (
            "Pitch decks, investor presentations, slide decks, PowerPoint, "
            "company presentations, business slides, proposal decks."
        ),
    },
    {
        "name": "Priya",
        "role": "Brand Identity",
        "description": (
            "Logos, brand identity, style guides, color palettes, typography systems, "
            "brand guidelines, wordmarks, visual identity, monograms."
        ),
    },
]

CONFIDENCE_THRESHOLD = 50

FIXED_QUESTIONS = [
    "What would you like designed?",
    "What is this design for? (e.g. product launch, campaign, client pitch, internal use)",
    "What is your deadline?",
    "Do you have any brand guidelines or references? (e.g. colors, fonts, mood boards, examples you like)",
    "What is your budget range?",
]

GROQ_MODEL = "llama-3.3-70b-versatile"
GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"
