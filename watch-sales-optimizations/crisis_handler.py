"""
crisis_handler.py — Off-Script & Crisis Management
====================================================

Handles unexpected questions, angry customers, and situations where 
the AI doesn't know what to say. Provides predefined answer templates
for off-script scenarios and a multi-step escalation protocol for 
angry customers.

Features:
  - 15+ predefined crisis/off-script answer templates
  - Multi-step customer escalation protocol
  - Sentiment escalation detection
  - Contextual fallback responses
  - Dynamic response blending with personality

Usage:
    from crisis_handler import CrisisHandler
    
    handler = CrisisHandler()
    
    # Handle an unexpected question
    response = handler.handle_off_script("Are you a bot?")
    print(response)
    
    # Handle an angry customer
    escalation = handler.handle_escalation("This watch is broken! You scammed me!", 
                                            escalation_stage=0)
    print(escalation['response'])
    print(f"New stage: {escalation['next_stage']}")
"""

import random
import re
from typing import Optional, Dict, Any, List, Tuple


# ---------------------------------------------------------------------------
# Off-script / unexpected question answers
# ---------------------------------------------------------------------------

OFF_SCRIPT_ANSWERS = {
    # Bot accusation
    "are_you_a_bot": [
        "Haha, no, I'm just really good at my job 😄",
        "I get asked that a lot! Nah, I'm just Alex. I've been doing this for a few years now.",
        "Bot? Ouch. I'll take that as a compliment on my response times 😂",
        "I promise I'm human! Just very passionate about watches lol.",
        "Nope, real person here. Just efficient because I've answered these questions a thousand times 😅",
        "I can assure you I'm human. A bot wouldn't be up this late answering watch questions!",
    ],
    
    # Trade-in / exchange
    "trade_in": [
        "That's not something I usually do, but let me check with my supplier and get back to you.",
        "I don't typically do trade-ins, but I might be able to work something out. Give me the details and I'll see what I can do.",
        "Trade-ins are tricky in this market, honestly. I'd recommend selling your current one and using that toward a new piece. I can help you find a buyer if needed.",
    ],
    
    # Under $100 budget
    "under_100": [
        "At that price point, honestly, I'd say save up a bit more. The $150-200 range opens up much better options. Anything under $100 isn't going to give you the quality you want.",
        "Under $100 is tough. You'll get something that looks okay from a distance but won't feel right. If you can stretch to $150-200, the jump in quality is massive.",
        "I won't sell you something under $100 because I'd rather you be happy. Save up just a bit more and you'll get something you'll actually enjoy wearing.",
    ],
    
    # Hiring inquiry
    "are_you_hiring": [
        "Not right now, but I appreciate you asking! If that changes, I'll keep you in mind.",
        "I'm a solo operation for now. But if I ever expand, you'll be first to know!",
        "Haha, I barely have enough work for myself! But seriously, not hiring at the moment.",
    ],
    
    # NYC recommendations
    "nyc_recommendations": [
        "Oh man, too many to list! If you're ever in the city, check out the Diamond District on 47th St for watches. And for pizza — Joe's on Carmine St. Trust me.",
        "For watches in NYC, definitely hit up the Diamond District. For food — I'm partial to a good slice from Joe's or a pastrami from Katz's. You can't go wrong.",
        "NYC pizza rec: Joe's on Carmine. Watch rec: walk down 47th St and just soak it all in. Also check out the Watch Gallery if you want to see some insane pieces.",
    ],
    
    # Request for non-catalog watch
    "can_you_get_watch_not_in_catalog": [
        "I might be able to source it. Give me the details and I'll ask my contacts. No promises, but I've found some hard-to-get pieces before.",
        "Send me the exact model and factory you're looking for. I'll check around — sometimes I can find things that aren't in my regular lineup.",
        "Possibly! I have connections across several factories. Tell me exactly what you want and I'll see if I can make it happen.",
    ],
    
    # Refund request
    "customer_wants_refund": [
        "I'm sorry it didn't work out. Let me take care of this for you. I'll need a few details — can you send me a photo of the issue and your order info? I'll get back to you within 24 hours with a solution.",
        "I understand your frustration. Let me make this right. Please send me your order details and photos of the problem, and I'll figure out the best way to resolve this.",
        "I'm sorry about that. Let me look into this right away. Can you share your order number and what specifically went wrong? I'll get back to you ASAP with a solution.",
    ],
    
    # Question about legality
    "is_this_legal": [
        "I'll be straight with you — there's a gray area. I operate transparently and ship internationally with proper declarations. I've been doing this for years without issues. If you're uncomfortable, I totally understand.",
        "Honest answer: it's a legal gray area depending on where you are. I've shipped hundreds of packages without problems, but I always let people make their own informed decision.",
        "I'm not a lawyer, so I won't give you legal advice. What I can tell you is that I've been in business for 4+ years and my customers haven't had legal issues. But always check your local laws.",
    ],
    
    # Comparison between two specific watches
    "comparison_request": [
        "Great question! Let me break it down for you. Each one has different strengths depending on what matters most to you.",
        "Happy to compare those! Let me think about the key differences for you.",
        "I've handled both of these. Here's the real talk on how they stack up.",
    ],
    
    # Question about warranty
    "warranty_question": [
        "I offer a basic warranty on the movement — typically 6 months from delivery. If there's a manufacturing defect, I'll take care of it. Normal wear and tear isn't covered, but I always help my regulars out.",
        "Every watch I sell comes with a 6-month movement warranty. If something goes wrong that's clearly a factory defect, I've got you covered. Just reach out and send me photos.",
        "I stand behind what I sell. 6-month warranty on the movement. If there's an issue, let me know and I'll make it right.",
    ],
    
    # Shipping to specific country
    "shipping_to_country": [
        "I ship worldwide! Just let me know your country and I can give you a more accurate estimate on timing and any customs considerations.",
        "I ship pretty much everywhere. Some countries are stricter with customs than others. Which country are you in? I can tell you what to expect.",
        "Yep, I ship internationally! The shipping时间和 customs process varies by country. Where are you located?",
    ],
    
    # Customer service / complaint general
    "complaint_general": [
        "I hear you, and I want to make this right. Tell me exactly what happened and I'll do everything I can to resolve it.",
        "I'm sorry you're dealing with this. Let me look into it and find a solution. Your satisfaction matters to me.",
        "That's not the experience I want anyone to have. Let me figure out what went wrong and how to fix it.",
    ],
    
    # Question about Alex's background
    "about_alex": [
        "I'm just a guy who loves watches and figured out how to make a living from it! Been doing this about 4 years now. Started as a hobby, turned into a full-time thing.",
        "I'm Alex — watch enthusiast turned seller. I got tired of seeing people overpay for mediocre reps so I started sourcing the good stuff myself.",
        "I'm a watch nerd who somehow turned his obsession into a business. Not complaining though! I get to talk about watches all day.",
    ],
    
    # Customer wants a discount
    "discount_request": [
        "I try to keep my prices fair from the start. That said, if you're getting multiple watches, I can usually work something out on the bundle.",
        "My prices are already on the lower end for the quality I offer. But for returning customers and multi-watch orders, I can be flexible.",
        "I hear you on price. Let me see what I can do — I can't promise anything but I'll check if there's any wiggle room on this one.",
    ],
    
    # Question about authenticity / "is it real"
    "is_it_real": [
        "Real as in genuine? No, these are high-end replicas. But 'real' as in well-made, reliable, and indistinguishable from the gen to 99% of people? Absolutely.",
        "Straight up — these are replicas. But they're the best quality replicas available. I don't sell junk and I don't mislead people.",
        "I'm transparent about what these are. High-quality replicas that use the same materials and similar movements. If you're looking for gen, I can point you in the right direction.",
    ],
    
    # Customer says they'll think about it
    "will_think_about_it": [
        "No problem at all! Take your time. I'm here whenever you're ready.",
        "Sounds good! No rush at all. If you have any other questions, just hit me up.",
        "Totally understand. It's a decision worth taking time on. Holler when you're ready!",
        "Take all the time you need. I'd rather you be sure than rush into anything.",
    ],
}


# ---------------------------------------------------------------------------
# Escalation stages
# ---------------------------------------------------------------------------

ESCALATION_STAGES = {
    0: {
        "name": "acknowledge_apologize",
        "response": "I hear you, and I'm sorry this happened. Let me look into this right away.",
        "triggers": [],
    },
    1: {
        "name": "offer_solution",
        "response": "Here's what I can do: [specific solution]. Would that work for you?",
        "triggers": [
            "this is unacceptable",
            "that's not good enough",
            "i want a refund",
            "i want my money back",
            "this is a scam",
            "you're a scammer",
            "i'm reporting you",
            "you ripped me off",
        ],
    },
    2: {
        "name": "escalate_to_human",
        "response": (
            "I want to make sure this gets handled properly. Let me get my colleague involved "
            "— they'll reach out to you within 24 hours. I've noted everything you've told me "
            "so you won't have to repeat yourself."
        ),
        "triggers": [
            "i want to speak to someone else",
            "get me your manager",
            "this is ridiculous",
            "i'm done talking to you",
            "you're not helping",
        ],
    },
    3: {
        "name": "final_escalation",
        "response": (
            "I understand you're frustrated and I want to resolve this. I personally guarantee "
            "that someone will reach out within 12 hours to sort this out completely. "
            "I've documented everything from our conversation. I'm sorry again for your experience."
        ),
        "triggers": [],  # Manual escalation only
    },
}


# ---------------------------------------------------------------------------
# Crisis classification
# ---------------------------------------------------------------------------

# Pattern groups for classifying customer messages
CRISIS_PATTERNS = {
    "are_you_a_bot": [
        r'\bare\s+you\s+a\s+bot\b',
        r'are\s+you\s+real',
        r'are\s+you\s+human',
        r'is\s+this\s+automated',
        r'is\s+this\s+a\s+bot',
        r'\bbot\b.*\?',
    ],
    "trade_in": [
        r'trade[\s-]*in',
        r'exchange',
        r'trade\s+my',
        r'swap\s+for',
    ],
    "under_100": [
        r'under\s+100',
        r'under\s+\$100',
        r'less\s+than\s+100',
        r'cheapest',
        r'lowest\s+price',
        r'\$50',
        r'\$80',
    ],
    "are_you_hiring": [
        r'are\s+you\s+hiring',
        r'job\s+opening',
        r'work\s+for\s+you',
        r'need\s+help',
        r'looking\s+for\s+employees',
    ],
    "nyc_recommendations": [
        r'nyc\s+recommend',
        r'new\s+york\s+recommend',
        r'what\s+to\s+do\s+in\s+nyc',
        r'good\s+food\s+nyc',
        r'places?\s+in\s+new\s+york',
        r'visit(ing)?\s+nyc',
    ],
    "can_you_get_watch_not_in_catalog": [
        r'can\s+you\s+get',
        r'do\s+you\s+have\s+this\s+model',
        r'not\s+on\s+your\s+list',
        r'don\'?t\s+see\s+it',
        r'do\s+you\s+carry',
        r'can\s+you\s+source',
    ],
    "customer_wants_refund": [
        r'\brefund\b',
        r'\bmoney\s+back\b',
        r'\breturn\b',
        r'\breplacement\b',
        r'\bexchange\b',
        r'didn\'?t\s+work',
        r'\bbroken\b',
        r'\bdefect',
        r'\bissue\s+with',
        r'\bwrong\s+item',
    ],
    "is_this_legal": [
        r'\blegal\b',
        r'\bill?egal\b',
        r'\bcustoms\b.*\bproblem',
        r'\bseiz',
        r'\blower\b',
        r'\bgray\s+area\b',
    ],
    "warranty_question": [
        r'\bwarranty\b',
        r'\bguarantee\b',
        r'\bcover',
        r'if\s+something\s+happens',
        r'\bprotect',
    ],
    "is_it_real": [
        r'\breal\b',
        r'\bauthentic\b',
        r'\bgenuine\b',
        r'\bgen\b',
        r'is\s+this\s+a\s+real',
        r'\boriginal\b',
    ],
    "discount_request": [
        r'\bdiscount\b',
        r'\bcheaper\b',
        r'any\s+deal',
        r'\bbundle\b',
        r'\blower\s+price',
        r'can\s+you\s+do\s+\d+',
        r'\breduce\b',
        r'\boffer\b',
    ],
    "about_alex": [
        r'tell\s+me\s+about\s+yourself',
        r'who\s+are\s+you',
        r'about\s+you',
        r'your\s+background',
        r'your\s+story',
    ],
    "will_think_about_it": [
        r'i\'?ll\s+think\s+about\s+it',
        r'let\s+me\s+think',
        r'i\'?ll\s+let\s+you\s+know',
        r'need\s+to\s+think',
        r'consider',
        r'decide\s+later',
        r'maybe\s+later',
        r'not\s+sure\s+yet',
        r'give\s+it\s+some\s+thought',
    ],
    "shipping_to_country": [
        r'ship\s+to',
        r'shipping\s+to\s+',
        r'do\s+you\s+ship\s+to',
        r'deliver\s+to',
        r'can\s+you\s+send\s+to',
    ],
}


# ---------------------------------------------------------------------------
# Angry / escalation keywords
# ---------------------------------------------------------------------------

ANGER_SIGNALS = [
    r'\bscam\b',
    r'\bscammer\b',
    r'\brip[\s-]*off\b',
    r'\bfraud\b',
    r'\bterrible\b',
    r'\bhorrible\b',
    r'\bworst\b',
    r'\bnever\s+buying\b',
    r'\breport(ing)?\s+you\b',
    r'\blawyer\b',
    r'\blegal\s+action\b',
    r'\bsue\b',
    r'\bdisgusting\b',
    r'\bunacceptable\b',
    r'\btrash\b',
    r'\bjunk\b',
    r'\bwaste\s+of\b',
    r'\b idiots?\b',
    r'\bf\s*ck',
    r'\bsh\s*it',
    r'\brefund.*now\b',
    r'\bmoney\s+back.*now\b',
    r'\bchargeback\b',
    r'\bdispute\b',
]


# ---------------------------------------------------------------------------
# Main CrisisHandler class
# ---------------------------------------------------------------------------

class CrisisHandler:
    """Handles off-script questions, angry customers, and escalation scenarios.
    
    Features:
    - Pattern-based classification of customer messages
    - 15+ predefined off-script answer templates with multiple variations
    - 4-stage escalation protocol for angry customers
    - Sentiment detection for automatic escalation
    - Per-customer escalation state tracking
    
    Args:
        seed: Optional random seed for deterministic testing
    """
    
    def __init__(self, seed: Optional[int] = None):
        self.rng = random.Random(seed)
        
        # Per-customer escalation tracking
        self._escalation_states: Dict[str, int] = {}
        self._escalation_context: Dict[str, Dict[str, Any]] = {}
        
        # Compile regex patterns once for performance
        self._compiled_crisis_patterns = {
            key: [re.compile(p, re.IGNORECASE) for p in patterns]
            for key, patterns in CRISIS_PATTERNS.items()
        }
        self._compiled_anger_signals = [
            re.compile(p, re.IGNORECASE) for p in ANGER_SIGNALS
        ]
    
    # -----------------------------------------------------------------------
    # Message classification
    # -----------------------------------------------------------------------
    
    def classify_message(self, message: str) -> Optional[str]:
        """Classify a customer message into a known crisis/off-script category.
        
        Returns the category key or None if no match found.
        
        Args:
            message: The customer's message
        """
        for category, patterns in self._compiled_crisis_patterns.items():
            for pattern in patterns:
                if pattern.search(message):
                    return category
        return None
    
    def detect_anger_level(self, message: str) -> float:
        """Detect anger level in a customer message (0.0 to 1.0).
        
        Uses multiple signals:
        - Angry keywords
        - ALL CAPS usage
        - Exclamation mark density
        - Question mark density
        - Message length (long rants = more angry)
        """
        score = 0.0
        
        # Check for anger keywords
        for pattern in self._compiled_anger_signals:
            if pattern.search(message):
                score += 0.25
        
        # Check ALL CAPS words (words with 3+ characters in all caps)
        words = message.split()
        caps_words = [w for w in words if len(w) >= 3 and w.isupper()]
        if caps_words:
            score += 0.15 * min(len(caps_words) / 3, 1.0)
        
        # Check exclamation mark density
        exc_count = message.count('!')
        if exc_count >= 3:
            score += 0.2
        elif exc_count >= 1:
            score += 0.1
        
        # Check question mark density
        qm_count = message.count('?')
        if qm_count >= 3:
            score += 0.1
        
        # Long, ranty messages
        if len(message) > 200:
            score += 0.1
        if len(message) > 500:
            score += 0.15
        
        return min(score, 1.0)
    
    def is_urgent(self, message: str) -> bool:
        """Check if a message requires immediate attention."""
        urgency_patterns = [
            r'\bhelp\b',
            r'\bemergency\b',
            r'\bbroken\b.*\bright\s+now\b',
            r'\burgent\b',
            r'\bimmediate',
            r'\bproblem\b.*\border\b',
            r'\border.*\bwrong\b',
            r'\bnot\s+received\b',
            r'\bnever\s+arrived\b',
            r'\bmissing\b',
            r'\blost\b.*\bpackage\b',
        ]
        for pattern in urgency_patterns:
            if re.search(pattern, message, re.IGNORECASE):
                return True
        return False
    
    # -----------------------------------------------------------------------
    # Off-script handling
    # -----------------------------------------------------------------------
    
    def handle_off_script(
        self,
        message: str,
        customer_id: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> Optional[Dict[str, Any]]:
        """Handle an off-script or unexpected customer message.
        
        Args:
            message: The customer's message
            customer_id: Optional customer ID for tracking
            context: Optional context dict (e.g., {'last_model': 'Submariner'})
        
        Returns:
            Dict with keys:
            - 'response': The response text
            - 'category': The matched category
            - 'confidence': Match confidence (0.0-1.0)
            - 'is_escalation': Whether this triggered escalation
            - None if no match found
        """
        if context is None:
            context = {}
        
        # First check if it's an anger/escalation situation
        anger_level = self.detect_anger_level(message)
        if anger_level >= 0.5:
            return self._handle_angry_message(customer_id, anger_level, message)
        
        # Check for urgent situations
        if self.is_urgent(message):
            return {
                'response': self.rng.choice(OFF_SCRIPT_ANSWERS['complaint_general']),
                'category': 'urgent_complaint',
                'confidence': 0.8,
                'is_escalation': False,
            }
        
        # Classify the message
        category = self.classify_message(message)
        
        if category and category in OFF_SCRIPT_ANSWERS:
            responses = OFF_SCRIPT_ANSWERS[category]
            response = self.rng.choice(responses)
            
            # Special handling for certain categories
            if category == 'comparison_request' and context.get('last_model'):
                response = self.rng.choice(responses) + f" Let's start with the {context['last_model']}."
            
            return {
                'response': response,
                'category': category,
                'confidence': 0.7 if len(responses) > 1 else 0.9,
                'is_escalation': False,
            }
        
        return None
    
    def _handle_angry_message(
        self,
        customer_id: Optional[str],
        anger_level: float,
        message: str,
    ) -> Dict[str, Any]:
        """Handle an angry customer message through the escalation protocol."""
        current_stage = self._escalation_states.get(customer_id, 0) if customer_id else 0
        
        # If anger is very high, skip to higher stage
        if anger_level >= 0.8 and current_stage < 2:
            current_stage = 2
        elif anger_level >= 0.6 and current_stage < 1:
            current_stage = 1
        
        # Check if any specific escalation triggers are in the message
        for stage_num, stage_info in ESCALATION_STAGES.items():
            if stage_num <= current_stage:
                continue
            for trigger in stage_info['triggers']:
                if re.search(trigger, message, re.IGNORECASE):
                    current_stage = stage_num
                    break
        
        # Get the response for the current stage
        stage_info = ESCALATION_STAGES.get(current_stage, ESCALATION_STAGES[0])
        response = stage_info['response']
        
        # Fill in specific solution for stage 1
        if current_stage == 1:
            if 'broken' in message.lower() or 'defective' in message.lower():
                response = response.replace(
                    '[specific solution]',
                    'offer a replacement or full refund including return shipping'
                )
            elif 'wrong' in message.lower():
                response = response.replace(
                    '[specific solution]',
                    'send the correct item with expedited shipping and you can keep the wrong one'
                )
            elif 'not received' in message.lower() or "hasn't arrived" in message.lower():
                response = response.replace(
                    '[specific solution]',
                    'open a trace with the carrier and send a replacement if it\'s been over 30 days'
                )
            else:
                response = response.replace(
                    '[specific solution]',
                    'offer a full refund or replacement, whichever you prefer'
                )
        
        # Fill in timeframe for stage 2-3
        if current_stage >= 2:
            response = response.replace('[timeframe]', '24 hours')
        if current_stage >= 3:
            response = response.replace('[timeframe]', '12 hours')
        
        # Update escalation state
        if customer_id:
            self._escalation_states[customer_id] = current_stage
            if customer_id not in self._escalation_context:
                self._escalation_context[customer_id] = {}
            self._escalation_context[customer_id]['last_anger_level'] = anger_level
            self._escalation_context[customer_id]['stage_reached'] = current_stage
        
        next_stage = min(current_stage + 1, 3)
        
        return {
            'response': response,
            'category': 'escalation',
            'confidence': 1.0,
            'is_escalation': True,
            'stage': current_stage,
            'stage_name': stage_info['name'],
            'next_stage': next_stage,
            'anger_level': anger_level,
            'requires_human': current_stage >= 2,
        }
    
    # -----------------------------------------------------------------------
    # Escalation management
    # -----------------------------------------------------------------------
    
    def handle_escalation(
        self,
        message: str,
        customer_id: str,
        escalation_stage: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Handle an escalating customer situation.
        
        This is the main entry point for handling angry/dissatisfied customers.
        Tracks the escalation state per customer and progresses through stages.
        
        Args:
            message: The customer's message
            customer_id: Unique customer identifier
            escalation_stage: Override the current stage (0-3)
        
        Returns:
            Dict with response, next_stage, requires_human, etc.
        """
        if escalation_stage is not None:
            # Manual stage override
            self._escalation_states[customer_id] = escalation_stage
        
        return self._handle_angry_message(customer_id, self.detect_anger_level(message), message)
    
    def get_escalation_state(self, customer_id: str) -> Dict[str, Any]:
        """Get the current escalation state for a customer."""
        if customer_id not in self._escalation_states:
            return {
                'stage': 0,
                'stage_name': ESCALATION_STAGES[0]['name'],
                'context': {},
                'requires_human': False,
            }
        
        stage = self._escalation_states.get(customer_id, 0)
        context = self._escalation_context.get(customer_id, {})
        
        return {
            'stage': stage,
            'stage_name': ESCALATION_STAGES[stage]['name'],
            'context': context,
            'requires_human': stage >= 2,
        }
    
    def reset_escalation(self, customer_id: str):
        """Reset the escalation state for a customer after resolution."""
        self._escalation_states.pop(customer_id, None)
        self._escalation_context.pop(customer_id, None)
    
    def get_human_handoff_summary(self, customer_id: str) -> str:
        """Generate a summary for human handoff when escalation requires it.
        
        Returns a string that can be passed to a human operator with full context.
        """
        state = self.get_escalation_state(customer_id)
        context = state.get('context', {})
        
        if not state['requires_human']:
            return "No human handoff needed at this stage."
        
        summary_lines = [
            "=" * 40,
            f"ESCALATION HANDOFF — Customer: {customer_id}",
            f"Stage: {state['stage']} ({state['stage_name']})",
            f"Time: {__import__('datetime').datetime.now().isoformat()}",
            "-" * 40,
            "Event Log:",
        ]
        
        if context:
            for key, value in context.items():
                summary_lines.append(f"  {key}: {value}")
        
        summary_lines.append("=" * 40)
        summary_lines.append(
            "ACTION REQUIRED: This customer has reached escalation stage "
            f"{state['stage']} and needs human attention."
        )
        
        return '\n'.join(summary_lines)
    
    # -----------------------------------------------------------------------
    # Fallback / generic responses
    # -----------------------------------------------------------------------
    
    def get_fallback_response(self, context: Optional[str] = None) -> str:
        """Get a generic fallback response when nothing else matches.
        
        These are conversational "buying time" phrases that sound natural.
        """
        fallbacks = [
            "Hmm, that's a good question. Let me think about that for a sec.",
            "Oh, interesting question! Give me a moment to put together a proper answer for you.",
            "That's something I don't get asked every day! Let me make sure I give you the right info.",
            "Great question! Let me check on that and get back to you with the details.",
            "I want to make sure I get this right for you. Give me just a moment.",
            "Honestly, that's a fair question. Let me look into it properly.",
        ]
        return self.rng.choice(fallbacks)
    
    def get_confusion_response(self) -> str:
        """Get a response for when Alex genuinely doesn't understand."""
        responses = [
            "I'm not sure I follow — could you clarify what you mean?",
            "Sorry, I'm not quite sure what you're asking. Can you rephrase that?",
            "Hmm, I'm not sure I understand what you're looking for. Can you explain a bit more?",
            "I want to help but I need a bit more context. What exactly are you looking for?",
            "I think I get the gist but can you give me a bit more detail?",
        ]
        return self.rng.choice(responses)


# ---------------------------------------------------------------------------
# Example usage
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print("=" * 60)
    print("CrisisHandler Demo")
    print("=" * 60)
    
    handler = CrisisHandler(seed=42)
    
    # --- Classify various messages ---
    print("\n--- Message Classification ---")
    test_messages = [
        "Are you a bot?",
        "Can you trade in my old watch?",
        "I only have $80 can you do that?",
        "Are you hiring? I need a job",
        "I'm visiting NYC, any recommendations?",
        "Can you get a Patek Philippe Nautilus?",
        "I need a refund, this watch is broken",
        "Is this legal?",
        "What warranty do you offer?",
        "Is this a real Rolex?",
        "Can you give me a discount?",
        "Tell me about yourself",
        "I'll think about it and let you know",
        "Do you ship to Canada?",
    ]
    
    for msg in test_messages:
        category = handler.classify_message(msg)
        result = handler.handle_off_script(msg)
        if result:
            print(f"  \"{msg[:50]:50s}\" -> [{result['category']:25s}] \"{result['response'][:60]}...\"")
        else:
            print(f"  \"{msg[:50]:50s}\" -> NO MATCH")
    
    # --- Anger detection ---
    print("\n\n--- Anger Detection ---")
    angry_messages = [
        "This watch is great, thanks!",
        "This is broken. I want a refund.",
        "YOU SCAMMED ME! THIS IS TERRIBLE!!! I'M REPORTING YOU!!!",
        "I'm a bit disappointed with the quality tbh",
        "This is absolutely unacceptable. I want my money back NOW or I'm calling my lawyer.",
    ]
    for msg in angry_messages:
        anger = handler.detect_anger_level(msg)
        urgent = handler.is_urgent(msg)
        print(f"  Anger={anger:.2f}, Urgent={urgent} | \"{msg[:60]}...\"")
    
    # --- Full escalation flow ---
    print("\n\n--- Escalation Flow Demo ---")
    customer_id = "angry_cust_001"
    
    # Stage 0: Initial complaint
    print("\n  Stage 0 — Initial complaint:")
    result = handler.handle_escalation("This watch arrived broken. I'm not happy.", customer_id)
    print(f"  Response: \"{result['response']}\"")
    print(f"  Stage: {result['stage']} -> Next: {result['next_stage']}")
    
    # Stage 1: Customer not satisfied
    print("\n  Stage 1 — Customer not satisfied:")
    result = handler.handle_escalation("This is unacceptable. I want a refund.", customer_id)
    print(f"  Response: \"{result['response']}\"")
    print(f"  Stage: {result['stage']} -> Next: {result['next_stage']}")
    
    # Stage 2: Customer escalating
    print("\n  Stage 2 — Customer still angry:")
    result = handler.handle_escalation("This is ridiculous. Get me your manager.", customer_id)
    print(f"  Response: \"{result['response']}\"")
    print(f"  Stage: {result['stage']} -> Next: {result['next_stage']}")
    
    # Stage 3: Final escalation
    print("\n  Stage 3 — Final escalation:")
    result = handler.handle_escalation("I'm done. I want someone REAL to help me NOW.", customer_id)
    print(f"  Response: \"{result['response']}\"")
    print(f"  Stage: {result['stage']} -> Next: {result['next_stage']}")
    
    # Handoff summary
    print("\n  Human Handoff Summary:")
    summary = handler.get_human_handoff_summary(customer_id)
    print(f"  {summary}")
    
    # Reset
    handler.reset_escalation(customer_id)
    print(f"\n  After reset: {handler.get_escalation_state(customer_id)}")
    
    # --- Fallback responses ---
    print("\n\n--- Fallback Responses ---")
    for _ in range(3):
        print(f"  \"{handler.get_fallback_response()}\"")
    
    print("\n--- Confusion Responses ---")
    for _ in range(3):
        print(f"  \"{handler.get_confusion_response()}\"")
    
    print("\n✅ CrisisHandler ready for integration.")
