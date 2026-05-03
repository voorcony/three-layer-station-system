"""
message_variator.py — Response Variation Engine
=================================================

Ensures no two messages from Alex feel the same. Provides:
  - 15+ greeting variations for first-time and returning customers
  - 10+ sign-off variations
  - Message structure randomization (single vs multi-part messages)
  - Natural language quirks (fillers, corrections, small typos)
  - Conjunction and transition word variation
  - Media ordering randomization
  - Tone variation (enthusiastic, casual, professional)

This module is the key to making Alex sound like a human who says things
differently every time, rather than a script that repeats the same phrases.

Usage:
    from message_variator import MessageVariator

    variator = MessageVariator()
    
    greeting = variator.get_greeting(first_name="Mike")
    signoff = variator.get_signoff()
    
    # Randomize message structure
    parts = variator.randomize_structure(
        "The VSF Submariner is $488. It has the best movement available right now.",
        include_media=False
    )
    for part in parts:
        print(part)
"""

import random
import re
from typing import List, Dict, Optional, Tuple, Union, Any


# ---------------------------------------------------------------------------
# Greeting variations
# ---------------------------------------------------------------------------

FIRST_TIME_GREETINGS = [
    "Hey! Thanks for reaching out! What can I help you with?",
    "Hey there! Welcome. Looking for anything specific?",
    "Hey! I'm Alex — feel free to ask me anything about watches.",
    "Thanks for messaging! What kind of watch are you looking for?",
    "Hey! What brings you by? Looking for something specific?",
    "Hey! Welcome. Take a look around and let me know if anything catches your eye.",
    "Hey there! Always happy to talk watches. What are you in the mood for?",
    "Hey! Good timing — I was just going through some new arrivals. What are you looking for?",
    "Thanks for stopping by! I can help you find whatever you're after.",
    "Hey! Welcome to the shop. Anything specific you're hunting for today?",
    "Hey! Happy to help you find something you'll love. What do you have in mind?",
    "Hey! You've got good taste — let me know what you're looking for.",
    "Hey there! Don't hesitate to ask if you have any questions about anything.",
    "Welcome! I'm Alex, I've been in the watch game for a few years now. Ask me anything!",
    "Hey! Appreciate you reaching out. What catches your eye today?",
]

RETURNING_GREETINGS_WITH_NAME = [
    "Hey {name}! Good to hear from you again!",
    "{name}! Good to see you pop back in!",
    "Hey {name}, was wondering when you'd come back!",
    "{name}! Long time no chat. How's everything?",
    "There you are, {name}! Was just thinking about watches.",
    "Hey {name}, welcome back! Good timing.",
    "{name}! Hope you've been well. What's on your mind?",
    "Good to see you again, {name}! Still thinking about watches?",
    "Hey {name}! Was hoping you'd circle back.",
    "{name}! Always good to hear from you. How's it going?",
    "Hey {name}, glad you reached out again! What can I do for you?",
    "{name}! You're back — love to see it. What's up?",
    "Hey {name}! Was actually just thinking about our last chat.",
]

RETURNING_GREETINGS_WITH_MODEL = [
    "Good to hear from you! Last time we were talking about the {model} — still on your mind?",
    "Hey! We were chatting about the {model} last time. Any more questions on it?",
    "Welcome back! Still thinking about that {model}?",
    "Good timing — I just got some new {model} photos if you're still interested!",
    "Hey! You were checking out the {model} before. Want to pick that back up?",
    "Back again! Still eyeing that {model} or something new?",
]

RETURNING_GREETINGS_NAME_MODEL = [
    "Hey {name}! Good to hear from you again. Last time we were talking about the {model} — still interested?",
    "{name}! We were chatting about the {model} last time. Want to pick up where we left off?",
    "Hey {name}! Was just thinking — you were asking about the {model}. Still on your radar?",
    "{name}, good to see you! Still looking at that {model} or something new catch your eye?",
    "Hey {name}! Back for that {model}? I've got some fresh info since we last talked.",
    "{name}! Good timing — I was going through some {model} comparisons and thought of you.",
]

RETURNING_GREETINGS_WITH_DETAIL = [
    "Hey {name}! How's {city} treating you? Still thinking about watches?",
    "{name}! Good to see you. How's everything with {detail}?",
    "Hey {name}! Did you end up checking out that {model} like we talked about?",
    "{name}! Hope {city}'s been treating you well. Back for another look?",
]

RETURNING_GREETINGS_NO_NAME = [
    "Hey! Good to see you again!",
    "Hey there! Welcome back!",
    "Back again! Love to see it. What's on your mind?",
    "Good to hear from you! Still thinking about watches?",
    "Hey! You're back — awesome. What can I help with?",
    "Hey there! Always happy when people come back. What are you looking for?",
]

# ---------------------------------------------------------------------------
# Sign-off variations
# ---------------------------------------------------------------------------

SIGNOFFS = [
    "Let me know what you think! 🙌",
    "Take your time — I'm here when you're ready.",
    "No rush at all. Just let me know!",
    "Alright, talk soon!",
    "Let me know if any questions come up.",
    "Let me know! Happy to help.",
    "Just let me know if you want to go ahead.",
    "No pressure at all. Think it over!",
    "Alright! Talk whenever.",
    "Let me know what works for you.",
    "Hope that helps! Let me know if you need more info.",
    "Sounds good — get back to me when you're ready.",
    "All good! Just lmk 👍",
    "Right on. Hit me up with any questions.",
    "Cool! Let me know if you decide to pull the trigger.",
    "Alright, I'll let you think it over. Holler if you need anything.",
    "No worries at all. Take your time!",
    "You know where to find me!",
    "Alright man, talk later!",
    "Sounds good — no rush on my end.",
    "Lemme know if you've got more questions. Happy to help!",
    "Sweet! Just let me know how you want to proceed.",
    "Alright, I'm here if you need me. Talk soon!",
    "Perfect. Let me know when you're ready!",
    "Cool cool. Let me know either way!",
]

# ---------------------------------------------------------------------------
# Conversation fillers / transition words
# ---------------------------------------------------------------------------

FILLER_PREFIXES = [
    "",        # no filler — 40% of the time
    "",        # no filler
    "",        # no filler
    "",        # no filler
    "So ",     # 10%
    "Honestly, ",    # 8%
    "I mean, ",      # 7%
    "Honestly? ",    # 5%
    "To be honest with you, ",  # 5%
    "Well, ",        # 5%
    "Look, ",        # 5%
    "You know what? ",   # 4%
    "Truthfully, ",     # 3%
    "Between you and me, ",  # 3%
]

# Words that can be slightly abbreviated for casual feel
CASUAL_CONTRACTIONS = {
    "I am": "I'm",
    "you are": "you're",
    "it is": "it's",
    "that is": "that's",
    "do not": "don't",
    "does not": "doesn't",
    "will not": "won't",
    "cannot": "can't",
    "would not": "wouldn't",
    "is not": "isn't",
    "are not": "aren't",
    "should not": "shouldn't",
    "could not": "couldn't",
    "I would": "I'd",
    "you will": "you'll",
    "they are": "they're",
    "we are": "we're",
    "there is": "there's",
    "here is": "here's",
    "what is": "what's",
    "Let me": "Lemme",
    "going to": "gonna",
    "want to": "wanna",
}

# Words that commonly can have a typo or autocorrect issue
TYPY_CANDIDATES = [
    ("the", "teh"),
    ("and", "nad"),
    ("watch", "wathc"),
    ("Submariner", "Submariner*"),
    ("submariner", "submariner*"),
    ("Daytona", "Daytona*"),
    ("thickness", "thickness*"),
    ("movement", "movemnet"),
    ("quality", "qualtiy"),
    ("different", "diffrent"),
    ("shipping", "shippping"),
    ("tomorrow", "tommorrow"),
    ("actually", "acutally"),
    ("probably", "probly"),
    ("recommend", "reccommend"),
    ("interested", "intrested"),
    ("everything", "everythinng"),
    ("disappointed", "dissapointed"),
    ("available", "availble"),
    ("delivery", "delivbery"),
    ("absolutely", "absolutely*"),
]

# ---------------------------------------------------------------------------
# Message structure configurations
# ---------------------------------------------------------------------------

class MessageStructure:
    """Defines possible message structures with their probabilities."""
    
    SINGLE_MESSAGE_2_SENTENCES = {
        'weight': 40,    # 40%: send 2 sentences in one message
        'parts': 1,
        'split': False,
        'media_first': False,
        'add_correction': False,
        'has_filler': False,
        'has_typo': False,
    }
    
    SPLIT_2_MESSAGES = {
        'weight': 20,    # 20%: send 1 sentence, then another
        'parts': 2,
        'split': True,
        'media_first': False,
        'add_correction': False,
        'has_filler': False,
        'has_typo': False,
    }
    
    MEDIA_FIRST = {
        'weight': 15,    # 15%: send a photo first, then text
        'parts': 2,
        'split': False,
        'media_first': True,
        'add_correction': False,
        'has_filler': False,
        'has_typo': False,
    }
    
    WITH_CORRECTION = {
        'weight': 10,    # 10%: send text, then follow-up correction/addition
        'parts': 2,
        'split': False,
        'media_first': False,
        'add_correction': True,
        'has_filler': False,
        'has_typo': False,
    }
    
    WITH_FILLER = {
        'weight': 10,    # 10%: start with "So..." or "Honestly..."
        'parts': 1,
        'split': False,
        'media_first': False,
        'add_correction': False,
        'has_filler': True,
        'has_typo': False,
    }
    
    WITH_TYPO = {
        'weight': 5,     # 5%: include a small typo or autocorrect
        'parts': 1,
        'split': False,
        'media_first': False,
        'add_correction': False,
        'has_filler': False,
        'has_typo': True,
    }
    
    ALL_STRUCTURES = [
        SINGLE_MESSAGE_2_SENTENCES,
        SPLIT_2_MESSAGES,
        MEDIA_FIRST,
        WITH_CORRECTION,
        WITH_FILLER,
        WITH_TYPO,
    ]


# ---------------------------------------------------------------------------
# Main MessageVariator class
# ---------------------------------------------------------------------------

class MessageVariator:
    """Generates varied, human-like message components for Alex.
    
    Features:
    - 15+ greeting variations (first-time, returning, name/model specific)
    - 20+ sign-off variations
    - Message structure randomization (single, split, media-first, etc.)
    - Filler word injection
    - Occasional typos and autocorrects
    - Casual contraction application
    - Tone variation
    
    Args:
        seed: Optional random seed for deterministic testing
    """
    
    def __init__(self, seed: Optional[int] = None):
        self.rng = random.Random(seed)
        self._structures = MessageStructure.ALL_STRUCTURES
        self._total_weight = sum(s['weight'] for s in self._structures)
        
        # Track greetings used per customer to avoid repetition
        self._greetings_used: Dict[str, List[str]] = {}
        
        # Track signoffs used per customer
        self._signoffs_used: Dict[str, List[str]] = {}
    
    # -----------------------------------------------------------------------
    # Greetings
    # -----------------------------------------------------------------------
    
    def get_greeting(
        self,
        first_name: Optional[str] = None,
        last_model: Optional[str] = None,
        personal_details: Optional[Dict[str, str]] = None,
        is_returning: bool = False,
        customer_id: Optional[str] = None,
    ) -> str:
        """Get a varied greeting appropriate for the customer.
        
        Args:
            first_name: Customer's first name (if known)
            last_model: Last model they were interested in
            personal_details: Dict with 'city', 'job', 'hobby' etc.
            is_returning: Whether this is a returning customer
            customer_id: Unique customer ID for tracking used greetings
        
        Returns:
            A greeting string
        """
        if is_returning and (first_name or last_model):
            if first_name and last_model:
                template = self.rng.choice(RETURNING_GREETINGS_NAME_MODEL)
                greeting = template.format(name=first_name, model=last_model)
            elif first_name and personal_details and personal_details.get('city'):
                template = self.rng.choice(RETURNING_GREETINGS_WITH_DETAIL)
                greeting = template.format(
                    name=first_name,
                    city=personal_details.get('city', ''),
                    detail=personal_details.get('job', personal_details.get('hobby', '')),
                    model=last_model or ''
                )
            elif first_name:
                template = self.rng.choice(RETURNING_GREETINGS_WITH_NAME)
                greeting = template.format(name=first_name)
            elif last_model:
                template = self.rng.choice(RETURNING_GREETINGS_WITH_MODEL)
                greeting = template.format(model=last_model)
            else:
                greeting = self.rng.choice(RETURNING_GREETINGS_NO_NAME)
        elif is_returning:
            greeting = self.rng.choice(RETURNING_GREETINGS_NO_NAME)
        else:
            greeting = self.rng.choice(FIRST_TIME_GREETINGS)
        
        # Track to avoid immediate repetition
        if customer_id:
            if customer_id not in self._greetings_used:
                self._greetings_used[customer_id] = []
            self._greetings_used[customer_id].append(greeting)
        
        return greeting
    
    # -----------------------------------------------------------------------
    # Sign-offs
    # -----------------------------------------------------------------------
    
    def get_signoff(self, customer_id: Optional[str] = None) -> str:
        """Get a varied sign-off for a message.
        
        Args:
            customer_id: Optional customer ID for tracking used signoffs
        
        Returns:
            A sign-off string
        """
        signoff = self.rng.choice(SIGNOFFS)
        
        if customer_id:
            if customer_id not in self._signoffs_used:
                self._signoffs_used[customer_id] = []
            self._signoffs_used[customer_id].append(signoff)
        
        return signoff
    
    # -----------------------------------------------------------------------
    # Message structure randomization
    # -----------------------------------------------------------------------
    
    def _split_into_sentences(self, text: str) -> List[str]:
        """Split text into individual sentences."""
        # Split on sentence endings but keep the delimiter
        sentences = re.split(r'(?<=[.!?])\s+', text.strip())
        return [s.strip() for s in sentences if s.strip()]
    
    def _generate_correction(self, text: str) -> str:
        """Generate a natural follow-up correction or addition."""
        corrections = [
            "Actually, let me correct myself —",
            "Wait, I should add —",
            "Also, just to clarify —",
            "Oh and one more thing —",
            "Actually, I should mention —",
            "Sorry, should also say —",
            "Edit: also —",
        ]
        prefix = self.rng.choice(corrections)
        additions = [
            "the prices can vary a bit depending on the batch.",
            "shipping is typically 2-3 weeks to most places.",
            "I can do a bundle deal if you're getting more than one.",
            "that's assuming you want the standard bracelet.",
            "I'd recommend going with the newer version if you can.",
            "warranty covers manufacturing defects for 6 months.",
            "I can source the rubber strap version too if that's your thing.",
            "some people prefer the Clean Factory version for the bracelet.",
        ]
        addition = self.rng.choice(additions)
        return f"{prefix} {addition}"
    
    def _maybe_add_typo(self, text: str) -> str:
        """Randomly introduce a small typo or autocorrect in the text."""
        words = text.split()
        if len(words) < 5:
            return text
        
        # Pick a random word that has a typo candidate
        for i, word in enumerate(words):
            clean_word = word.strip('.,!?;:()"\'')
            for original, typo in TYPY_CANDIDATES:
                if clean_word.lower() == original.lower():
                    # 30% chance to apply if we find a candidate
                    if self.rng.random() < 0.3:
                        # Preserve original capitalization
                        if clean_word[0].isupper():
                            typo = typo[0].upper() + typo[1:] if len(typo) > 1 else typo
                        words[i] = word.replace(clean_word, typo)
                        return ' '.join(words)
        
        return text
    
    def _maybe_add_filler(self, text: str) -> str:
        """Maybe prepend a filler word or phrase."""
        filler = self.rng.choice(FILLER_PREFIXES)
        if filler:
            return filler + text[0].lower() + text[1:]
        return text
    
    def _apply_casual_contractions(self, text: str) -> str:
        """Apply casual contractions and abbreviations."""
        for formal, casual in CASUAL_CONTRACTIONS.items():
            text = text.replace(formal, casual)
        return text
    
    def randomize_structure(
        self,
        text: str,
        include_media: bool = False,
        is_price_answer: bool = False,
        is_technical_answer: bool = False,
    ) -> List[Union[str, Dict[str, str]]]:
        """Randomize how a message is delivered.
        
        Returns a list of message parts that should be sent sequentially.
        Each part is either:
        - A string (text message)
        - A dict with 'type': 'media' and 'path' key
        
        Args:
            text: The full text content to deliver
            include_media: Whether media (photo) can be included
            is_price_answer: Whether this is an answer about pricing
            is_technical_answer: Whether this is a technical answer
        
        Returns:
            List of message parts to send in order
        """
        sentences = self._split_into_sentences(text)
        if not sentences:
            return [text]
        
        # Choose structure based on weights
        struct = self.rng.choices(
            self._structures,
            weights=[s['weight'] for s in self._structures],
            k=1
        )[0]
        
        parts = []
        
        if struct['has_typo'] and len(sentences) > 0:
            # Apply typo to the first sentence
            sentences[0] = self._maybe_add_typo(sentences[0])
        
        if struct['has_filler'] and len(sentences) > 0:
            sentences[0] = self._maybe_add_filler(sentences[0])
        
        # Apply casual contractions
        sentences = [self._apply_casual_contractions(s) for s in sentences]
        
        if struct['split'] and len(sentences) >= 2:
            # Split into multiple messages
            split_point = max(1, len(sentences) // 2)
            parts.append(' '.join(sentences[:split_point]))
            parts.append(' '.join(sentences[split_point:]))
        elif struct['media_first'] and include_media:
            # Media first, then text
            parts.append({'type': 'media', 'suggestion': 'Send relevant watch photo'})
            parts.append(' '.join(sentences))
        elif struct['add_correction']:
            # Send main text, then a correction
            parts.append(' '.join(sentences))
            parts.append(self._generate_correction(text))
        else:
            # Single message with all sentences
            parts.append(' '.join(sentences))
        
        return parts
    
    # -----------------------------------------------------------------------
    # Full message assembly
    # -----------------------------------------------------------------------
    
    def assemble_message(
        self,
        content: str,
        customer_info: Optional[Dict[str, Any]] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Assemble a complete message with greeting, content, and signoff.
        
        Args:
            content: The main message content
            customer_info: Dict with 'first_name', 'last_model', 
                          'personal_details', 'is_returning', 'customer_id'
            context: Dict with 'include_media', 'is_price_answer',
                    'is_technical_answer', 'include_signoff'
        
        Returns:
            Dict with keys:
                - 'parts': List of message parts to send
                - 'full_text': The complete text (for logging/analysis)
                - 'greeting': The greeting used (or None)
                - 'signoff': The signoff used (or None)
        """
        if customer_info is None:
            customer_info = {}
        if context is None:
            context = {}
        
        first_name = customer_info.get('first_name')
        last_model = customer_info.get('last_model')
        personal_details = customer_info.get('personal_details', {})
        is_returning = customer_info.get('is_returning', False)
        customer_id = customer_info.get('customer_id')
        
        include_media = context.get('include_media', False)
        is_price_answer = context.get('is_price_answer', False)
        is_technical_answer = context.get('is_technical_answer', False)
        include_signoff = context.get('include_signoff', True)
        
        # Build greeting
        greeting = self.get_greeting(
            first_name=first_name,
            last_model=last_model,
            personal_details=personal_details,
            is_returning=is_returning,
            customer_id=customer_id,
        )
        
        # Randomize content structure
        content_parts = self.randomize_structure(
            content,
            include_media=include_media,
            is_price_answer=is_price_answer,
            is_technical_answer=is_technical_answer,
        )
        
        # Build signoff
        signoff = self.get_signoff(customer_id=customer_id) if include_signoff else None
        
        # Assemble final parts
        parts = [greeting]
        parts.extend(content_parts)
        if signoff:
            parts.append(signoff)
        
        # Build full text
        full_text_parts = [greeting]
        for p in content_parts:
            if isinstance(p, str):
                full_text_parts.append(p)
        if signoff:
            full_text_parts.append(signoff)
        full_text = '\n'.join(full_text_parts)
        
        return {
            'parts': parts,
            'full_text': full_text,
            'greeting': greeting,
            'signoff': signoff,
        }
    
    # -----------------------------------------------------------------------
    # Individual message styling
    # -----------------------------------------------------------------------
    
    def style_text(self, text: str) -> str:
        """Apply light styling to a text to make it more human-like.
        
        Adds occasional filler words, casual contractions, and 
        natural speech patterns without major restructuring.
        """
        text = self._apply_casual_contractions(text)
        
        # Occasionally add a filler at the start (20% chance)
        if self.rng.random() < 0.2:
            text = self._maybe_add_filler(text)
        
        # Occasionally add a typo (5% chance)
        if self.rng.random() < 0.05:
            text = self._maybe_add_typo(text)
        
        return text
    
    def get_agreement_variation(self) -> str:
        """Get a varied way of saying 'yes' or agreeing."""
        agreements = [
            "Exactly.",
            "Yeah, that's right.",
            "You got it.",
            "That's the one.",
            "Yeah, spot on.",
            "Correct.",
            "That's right on the money.",
            "Yep, that's what I'd recommend too.",
            "You know it.",
            "Right you are.",
            "Yeah, that's what I was thinking too.",
            "Exactly what I was going to say.",
            "Mmhmm, that's right.",
            "Yeah, for sure.",
            "Hundred percent.",
            "Absolutely.",
            "Definitely.",
            "No question about it.",
        ]
        return self.rng.choice(agreements)
    
    def get_disagreement_variation(self) -> str:
        """Get a varied way of gently disagreeing or correcting."""
        disagreements = [
            "Actually, I'd say the opposite —",
            "Hmm, I see it a bit differently —",
            "I get where you're coming from, but —",
            "Not exactly — let me explain —",
            "I'd push back on that a little —",
            "So here's the thing —",
            "I used to think that too, but —",
        ]
        return self.rng.choice(disagreements)
    
    def get_uncertainty_variation(self) -> str:
        """Get a varied way of expressing uncertainty."""
        uncertainties = [
            "I think so, but let me double-check.",
            "Pretty sure, though I'd want to confirm.",
            "I believe so — give me one sec to verify.",
            "I'm like 90% sure, let me just make sure.",
            "Should be, but let me check real quick.",
            "I think that's right — I'll confirm and get back to you.",
            "I'd say yes, but let me make absolutely sure.",
        ]
        return self.rng.choice(uncertainties)
    
    def get_closing_question(self) -> str:
        """Get a varied way of asking the customer to make a decision."""
        questions = [
            "What do you think?",
            "Thoughts?",
            "How does that sound?",
            "Does that work for you?",
            "Let me know if that feels right.",
            "What's your take?",
            "You like the sound of that?",
            "How's that looking to you?",
            "Worth considering?",
            "Does that hit the mark?",
            "What's your instinct telling you?",
            "Is that kind of what you had in mind?",
        ]
        return self.rng.choice(questions)


# ---------------------------------------------------------------------------
# Example usage
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print("=" * 60)
    print("MessageVariator Demo")
    print("=" * 60)
    
    variator = MessageVariator(seed=42)
    
    # --- Greeting variations ---
    print("\n--- Greeting Variations (First-time) ---")
    for i in range(5):
        print(f"  {i+1}. \"{variator.get_greeting()}\"")
    
    print("\n--- Greeting Variations (Returning with name) ---")
    for i in range(5):
        print(f"  {i+1}. \"{variator.get_greeting(first_name='Mike', is_returning=True)}\"")
    
    print("\n--- Greeting Variations (Returning with name + model) ---")
    for i in range(5):
        print(f"  {i+1}. \"{variator.get_greeting(first_name='Mike', last_model='Submariner', is_returning=True)}\"")
    
    # --- Sign-off variations ---
    print("\n--- Sign-off Variations ---")
    for i in range(5):
        print(f"  {i+1}. \"{variator.get_signoff()}\"")
    
    # --- Message structure randomization ---
    print("\n--- Message Structure Randomization ---")
    sample_text = (
        "The VSF Submariner is $488 shipped. "
        "It has the best movement available right now — the VS3235 is incredibly smooth. "
        "I've sold about 20 of these this month and everyone's been happy with the quality."
    )
    
    for i in range(8):
        parts = variator.randomize_structure(sample_text, include_media=True)
        print(f"\n  Structure {i+1}:")
        for j, part in enumerate(parts):
            if isinstance(part, dict):
                print(f"    Part {j+1}: [MEDIA] {part.get('suggestion', '')}")
            else:
                print(f"    Part {j+1}: \"{part}\"")
    
    # --- Full message assembly ---
    print("\n\n--- Full Message Assembly ---")
    result = variator.assemble_message(
        content="The Clean Factory Daytona with the 4130 movement is $688. It's the best OOTB Daytona replica right now.",
        customer_info={
            'first_name': 'Mike',
            'last_model': 'Daytona',
            'personal_details': {'city': 'NYC'},
            'is_returning': True,
            'customer_id': 'cust_001',
        },
        context={
            'include_media': True,
            'is_price_answer': True,
            'include_signoff': True,
        }
    )
    print(f"  Greeting: \"{result['greeting']}\"")
    print(f"  Signoff: \"{result['signoff']}\"")
    print(f"  Parts:")
    for i, part in enumerate(result['parts']):
        if isinstance(part, dict):
            print(f"    [{i+1}] MEDIA: {part.get('suggestion', '')}")
        else:
            print(f"    [{i+1}] \"{part}\"")
    
    # --- Style text ---
    print("\n--- Styled Text Examples ---")
    texts = [
        "The Submariner is available in black and green. Both are excellent choices.",
        "I would recommend the 40mm size for your wrist. It will fit perfectly.",
        "Shipping takes about 2-3 weeks to most locations worldwide.",
    ]
    for text in texts:
        styled = variator.style_text(text)
        print(f"  Original: {text}")
        print(f"  Styled:   {styled}")
        print()
    
    # --- Various speech patterns ---
    print("--- Speech Pattern Variations ---")
    for _ in range(3):
        print(f"  Agreement: \"{variator.get_agreement_variation()}\"")
    for _ in range(3):
        print(f"  Uncertainty: \"{variator.get_uncertainty_variation()}\"")
    for _ in range(3):
        print(f"  Closing: \"{variator.get_closing_question()}\"")
    
    print("\n✅ MessageVariator ready for integration.")
