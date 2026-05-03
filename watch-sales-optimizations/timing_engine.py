"""
timing_engine.py — Human-Like Response Timing Module
=====================================================

Controls WHEN and HOW FAST Alex responds to customers on WhatsApp.
Simulates realistic human timing patterns including:
  - Variable response delays based on time of day, message complexity, customer behavior
  - Offline hours with auto-reply scheduling
  - Busy periods (1-2x/week slower replies)
  - Typing indicator simulation
  - Peak/off-peak human hour adjustments
  - Customer energy matching

Usage:
    from timing_engine import TimingEngine

    engine = TimingEngine(seed=42)  # seed for deterministic testing
    delay = engine.calculate_delay(
        customer_message="How much is the Submariner?",
        customer_history={"avg_response_time": 120, "message_count": 5},
        conversation_context={"total_messages": 3, "is_first_message": True}
    )
    print(f"Wait {delay:.0f} seconds before replying")

    # Check if auto-reply should be sent (offline hours)
    auto_reply = engine.get_auto_reply()
    if auto_reply:
        print(f"Send auto-reply: {auto_reply}")
"""

import random
import time
import json
import math
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any, Union, List, Tuple

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Eastern Time offset from UTC (simplified: EST = UTC-5, EDT = UTC-4)
# We check current UTC and compute ET manually.
EST_OFFSET = -5  # Standard time
EDT_OFFSET = -4  # Daylight time (Mar-Nov)

# Keywords that indicate a simple, non-urgent message
SIMPLE_REPLY_KEYWORDS = [
    "ok", "okay", "k", "kk", "thanks", "thx", "ty", "thank you",
    "cool", "nice", "👍", "✅", "🙏", "😊", "got it", "gotcha",
    "sure", "yep", "yeah", "no problem", "works", "perfect",
]

# Keywords that indicate a price question
PRICE_KEYWORDS = [
    "price", "cost", "how much", "pricing", "$$", "$",
    "expensive", "cheap", "affordable", "budget", "worth",
    "value", "deal", "offer", "shipping cost", "total",
]

# Keywords that indicate a technical question
TECHNICAL_KEYWORDS = [
    "movement", "automatic", "quartz", "mechanical", "water resistant",
    "waterproof", "sapphire", "crystal", "bracelet", "clasp",
    "lume", "luminescence", "power reserve", "thickness", "diameter",
    "weight", "material", "steel", "gold", "ceramic", "bezel",
    "factory", "vs", "vsfa", "zrf", "clean", "bpf", "gmf",
    "clone", "modified", "replica", "AAA", "Swiss",
]

# ---------------------------------------------------------------------------
# Time helpers
# ---------------------------------------------------------------------------

def _is_dst(dt: datetime) -> bool:
    """Check if a datetime falls within US Eastern Daylight Time."""
    year = dt.year
    # March DST start: second Sunday at 2:00 AM EDT
    march_start = datetime(year, 3, 8, 2, 0, 0, tzinfo=timezone.utc)
    while march_start.weekday() != 6:
        march_start += timedelta(days=1)
    march_start += timedelta(weeks=1)  # second Sunday
    # November DST end: first Sunday at 2:00 AM EST
    nov_end = datetime(year, 11, 1, 2, 0, 0, tzinfo=timezone.utc)
    while nov_end.weekday() != 6:
        nov_end += timedelta(days=1)
    return march_start <= dt.replace(tzinfo=timezone.utc) < nov_end


def current_hour_et() -> int:
    """Return the current hour (0-23) in US Eastern Time."""
    now_utc = datetime.now(timezone.utc)
    offset = EDT_OFFSET if _is_dst(now_utc) else EST_OFFSET
    now_et = now_utc + timedelta(hours=offset)
    return now_et.hour


def current_minute_et() -> int:
    """Return the current minute (0-59) in US Eastern Time."""
    now_utc = datetime.now(timezone.utc)
    offset = EDT_OFFSET if _is_dst(now_utc) else EST_OFFSET
    now_et = now_utc + timedelta(hours=offset)
    return now_et.minute


def is_offline_hours(hour: Optional[int] = None) -> bool:
    """Check if current time is in offline hours (12am-7am ET)."""
    if hour is None:
        hour = current_hour_et()
    return 0 <= hour < 7


def is_peak_human_hours(hour: Optional[int] = None) -> bool:
    """Check if current time is in peak human hours.
    
    Peak hours: 10am-2pm (midday) and 6pm-10pm (evening).
    """
    if hour is None:
        hour = current_hour_et()
    return (10 <= hour <= 14) or (18 <= hour <= 22)


def is_late_hours(hour: Optional[int] = None) -> bool:
    """Check if current time is late (11pm-12am or 7am-9am)."""
    if hour is None:
        hour = current_hour_et()
    return (7 <= hour < 10) or (23 == hour)


# ---------------------------------------------------------------------------
# Message classification
# ---------------------------------------------------------------------------

def is_simple_reply(message: str) -> bool:
    """Check if a message is a simple acknowledgment that needs fast reply."""
    msg_lower = message.lower().strip()
    for kw in SIMPLE_REPLY_KEYWORDS:
        if msg_lower == kw or msg_lower.startswith(kw):
            return True
    # Also check single emoji messages
    if len(msg_lower) <= 2 and any(c in msg_lower for c in ["👍", "✅", "🙏", "😊", "❤️", "🔥"]):
        return True
    return False


def is_price_question(message: str) -> bool:
    """Check if message is asking about price."""
    msg_lower = message.lower()
    return any(kw in msg_lower for kw in PRICE_KEYWORDS)


def is_technical_question(message: str) -> bool:
    """Check if message is asking a technical question."""
    msg_lower = message.lower()
    return any(kw in msg_lower for kw in TECHNICAL_KEYWORDS)


def message_complexity_score(message: str) -> float:
    """Return a complexity score (0.0 to 2.0) for a message.
    
    0.0 = simple reply, 1.0 = normal, 2.0 = highly complex.
    """
    if is_simple_reply(message):
        return 0.0
    
    score = 1.0
    if is_price_question(message):
        score += 0.5
    if is_technical_question(message):
        score += 0.6
    
    # Longer messages tend to be more complex
    word_count = len(message.split())
    if word_count > 20:
        score += 0.3
    if word_count > 50:
        score += 0.4
    
    # Question marks indicate inquiry
    if "?" in message:
        score += 0.2
    
    return min(score, 2.0)


# ---------------------------------------------------------------------------
# Busy period tracking
# ---------------------------------------------------------------------------

class BusyPeriodTracker:
    """Tracks 'busy' periods where Alex is slower to reply.
    
    Busy periods occur 1-2 times per week, lasting 2-4 hours each.
    Persists state to a JSON file if path is provided.
    """
    
    def __init__(self, state_path: Optional[str] = None, seed: Optional[int] = None):
        self.rng = random.Random(seed)
        self.state_path = state_path
        self._current_busy_end: Optional[datetime] = None
        self._last_busy_check: Optional[datetime] = None
        self._busy_this_week: int = 0
        self._week_number: int = -1
        self._load_state()
    
    def _load_state(self):
        if self.state_path:
            try:
                with open(self.state_path, 'r') as f:
                    data = json.load(f)
                    self._busy_this_week = data.get('busy_this_week', 0)
                    self._week_number = data.get('week_number', -1)
                    end_str = data.get('current_busy_end')
                    if end_str:
                        self._current_busy_end = datetime.fromisoformat(end_str)
            except (FileNotFoundError, json.JSONDecodeError, ValueError):
                pass
    
    def _save_state(self):
        if self.state_path:
            data = {
                'busy_this_week': self._busy_this_week,
                'week_number': self._week_number,
                'current_busy_end': self._current_busy_end.isoformat() if self._current_busy_end else None,
            }
            with open(self.state_path, 'w') as f:
                json.dump(data, f)
    
    def is_busy_now(self) -> bool:
        """Check if Alex is currently in a busy period."""
        now = datetime.now()
        current_week = now.isocalendar()[1]
        
        # Reset weekly counter if week changed
        if current_week != self._week_number:
            self._week_number = current_week
            self._busy_this_week = 0
            self._current_busy_end = None
        
        # Check if currently in a busy period
        if self._current_busy_end and now < self._current_busy_end:
            return True
        
        # Check if we should start a new busy period (1-2 times per week)
        if self._busy_this_week < 2:
            if self._last_busy_check is None:
                self._last_busy_check = now
                return False
            
            # Random chance to start a busy period (higher on weekdays)
            hours_since_check = (now - self._last_busy_check).total_seconds() / 3600
            if hours_since_check > 24:  # Only check once per day
                self._last_busy_check = now
                # 30% chance if we haven't had any this week, 15% if we've had 1
                chance = 0.30 if self._busy_this_week == 0 else 0.15
                if self.rng.random() < chance:
                    busy_hours = self.rng.uniform(2.0, 4.0)
                    self._current_busy_end = now + timedelta(hours=busy_hours)
                    self._busy_this_week += 1
                    self._save_state()
                    return True
        
        return False


# ---------------------------------------------------------------------------
# Typing simulation
# ---------------------------------------------------------------------------

def simulate_typing_time(message: str, rng: Optional[random.Random] = None) -> float:
    """Calculate a realistic 'typing' time for a given message.
    
    Short message (1-3 words): 3-8 seconds
    Medium message (4-15 words): 8-20 seconds
    Long message (16-40 words): 15-40 seconds
    Very long message (40+ words): 30-60 seconds
    
    Includes pauses for thinking (mid-sentence pauses of 2-5 seconds).
    """
    if rng is None:
        rng = random.Random()
    
    word_count = len(message.split())
    
    if word_count <= 3:
        base_time = rng.uniform(3, 8)
    elif word_count <= 15:
        base_time = rng.uniform(8, 20)
    elif word_count <= 40:
        base_time = rng.uniform(15, 40)
    else:
        base_time = rng.uniform(30, 60)
    
    # Add occasional pauses for longer messages (simulates thinking)
    if word_count > 10 and rng.random() < 0.3:
        base_time += rng.uniform(2, 5)
    if word_count > 25 and rng.random() < 0.4:
        base_time += rng.uniform(3, 8)
    
    # Add small random jitter
    base_time *= rng.uniform(0.85, 1.15)
    
    return round(base_time, 1)


# ---------------------------------------------------------------------------
# Main TimingEngine
# ---------------------------------------------------------------------------

class TimingEngine:
    """The main engine for calculating human-like response delays.
    
    Features:
    - Base delay randomization (30-180s for first reply)
    - Follow-up delay matching (mirrors customer reply speed)
    - Complexity-based delay adjustments
    - Time-of-day adjustments (peak/offline/late hours)
    - Busy period simulation
    - Typing indicator timing
    - Offline auto-reply scheduling
    
    Args:
        seed: Optional random seed for deterministic testing
        state_path: Optional path to persist busy period state
    """
    
    def __init__(self, seed: Optional[int] = None, state_path: Optional[str] = None):
        self.rng = random.Random(seed)
        self.busy_tracker = BusyPeriodTracker(state_path, seed=self.rng.randint(0, 2**31) if seed is None else seed + 1)
        
        # Track last reply times per customer to avoid instant follow-ups
        self._last_reply_times: Dict[str, datetime] = {}
        
        # Offline auto-reply tracking — keyed by customer_id, value = (has_sent_auto_reply, auto_reply_time)
        self._auto_reply_sent: Dict[str, bool] = {}
    
    def calculate_delay(
        self,
        customer_message: str,
        customer_history: Optional[Dict[str, Any]] = None,
        conversation_context: Optional[Dict[str, Any]] = None,
        customer_id: Optional[str] = None,
    ) -> float:
        """Calculate the delay (in seconds) before Alex should reply.
        
        Args:
            customer_message: The customer's latest message text
            customer_history: Dict with keys like:
                - avg_response_time (float): customer's avg response time in seconds
                - message_count (int): total messages in this conversation
                - last_response_time (float): seconds since customer last replied
            conversation_context: Dict with keys like:
                - total_messages (int): total messages exchanged so far
                - is_first_message (bool): True if this is the first message from customer
                - has_media (bool): True if message contains media
            customer_id: Optional unique customer ID for state tracking
        
        Returns:
            Delay in seconds (float) to wait before replying
        """
        if customer_history is None:
            customer_history = {}
        if conversation_context is None:
            conversation_context = {}
        
        avg_customer_response = customer_history.get('avg_response_time', None)
        total_messages = conversation_context.get('total_messages', 0)
        is_first = conversation_context.get('is_first_message', False)
        
        # ---- 1. BASE DELAY ----
        if is_first or total_messages <= 1:
            # First response in a conversation: 30-180 seconds
            base_delay = self.rng.uniform(30, 180)
        else:
            # Follow-up: 10-120 seconds base
            base_delay = self.rng.uniform(10, 120)
        
        # ---- 2. CUSTOMER ENERGY MATCHING ----
        if avg_customer_response is not None:
            if avg_customer_response < 60:
                # They reply very fast (< 1 min) -> match energy, slightly slower
                base_delay *= self.rng.uniform(0.6, 1.0)
            elif avg_customer_response < 300:
                # They reply within 5 min -> slightly faster
                base_delay *= self.rng.uniform(0.8, 1.2)
            elif avg_customer_response < 1800:
                # They reply within 30 min -> moderate pace
                base_delay *= self.rng.uniform(1.0, 1.5)
            else:
                # They take > 30 min -> relaxed pace
                base_delay *= self.rng.uniform(1.3, 2.0)
        
        # ---- 3. MESSAGE COMPLEXITY ADJUSTMENT ----
        complexity = message_complexity_score(customer_message)
        if complexity >= 1.5:
            # Complex question: add 45-120 seconds for "thinking/checking"
            base_delay += self.rng.uniform(45, 120)
        elif complexity >= 0.8:
            # Moderately complex: add 15-45 seconds
            base_delay += self.rng.uniform(15, 45)
        elif complexity <= 0.2 and not is_first:
            # Simple reply: 10-60 seconds (faster)
            base_delay = self.rng.uniform(10, 60)
        
        # ---- 4. TIME OF DAY ADJUSTMENT ----
        current_hour = current_hour_et()
        
        if is_offline_hours(current_hour):
            # Offline hours (12am-7am): very slow or auto-reply
            base_delay += self.rng.uniform(600, 3600)  # 10min-1hr
        elif is_late_hours(current_hour):
            # Late hours (7-10am, 11pm-12am): slower
            base_delay += self.rng.uniform(120, 900)  # 2-15min
        elif is_peak_human_hours(current_hour):
            # Peak hours (10am-2pm, 6pm-10pm): faster
            base_delay *= self.rng.uniform(0.6, 0.9)
        
        # ---- 5. BUSY PERIOD CHECK ----
        if self.busy_tracker.is_busy_now():
            base_delay += self.rng.uniform(7200, 14400)  # 2-4 hours
        
        # ---- 6. CONVERSATION MATURITY ----
        if total_messages > 20:
            # As conversation goes on, replies become more casual/varied
            base_delay *= self.rng.uniform(0.8, 1.3)
        if total_messages > 50:
            base_delay *= self.rng.uniform(0.7, 1.4)
        
        # ---- 7. RANDOM JITTER ----
        jitter = self.rng.uniform(0.5, 2.0)
        final_delay = base_delay * jitter
        
        # ---- 8. MIN/MAX BOUNDARIES ----
        final_delay = max(5.0, final_delay)   # Never reply in < 5 seconds
        if is_offline_hours(current_hour):
            final_delay = min(final_delay, 7200)  # Cap at 2hr during offline
        else:
            final_delay = min(final_delay, 3600)  # Cap at 1hr during normal hours
        
        # Track last reply time for this customer
        if customer_id:
            self._last_reply_times[customer_id] = datetime.now()
        
        return round(final_delay, 1)
    
    def get_typing_time(self, message: str) -> float:
        """Simulate how long Alex would spend typing a message.
        
        Returns time in seconds that represents realistic typing + thinking.
        """
        return simulate_typing_time(message, self.rng)
    
    def should_send_auto_reply(self, customer_id: str) -> bool:
        """Check if we should send the offline auto-reply to this customer.
        
        Auto-reply is sent once per offline period per customer.
        """
        if customer_id in self._auto_reply_sent and self._auto_reply_sent[customer_id]:
            return False
        return is_offline_hours()
    
    def mark_auto_reply_sent(self, customer_id: str):
        """Mark that auto-reply has been sent to this customer."""
        self._auto_reply_sent[customer_id] = True
    
    def get_auto_reply_message(self) -> str:
        """Get the offline auto-reply message."""
        messages = [
            "Hey, saw your message! I'm heading to bed but I'll get back to you first thing in the morning 🙏",
            "Hey! Just about to turn in for the night. I'll reply to you first thing tomorrow morning!",
            "Hey, catching this before I crash. I'll get back to you in the morning — talk then!",
        ]
        return self.rng.choice(messages)
    
    def get_follow_up_delay_for_offline(
        self,
        auto_reply_time: Optional[datetime] = None,
    ) -> float:
        """Calculate when to follow up after an auto-reply was sent overnight.
        
        Returns delay in seconds from now until the proper reply should be sent
        (sometime after 7am ET).
        """
        now = datetime.now()
        now_hour = current_hour_et()
        
        if now_hour < 7:
            # Still before 7am — schedule reply for 7:00-8:30am
            target_hour = 7 + self.rng.uniform(0, 1.5)
            target_minute = self.rng.randint(0, 59)
            
            # Calculate seconds until target time
            now_utc = datetime.now(timezone.utc)
            offset = EDT_OFFSET if _is_dst(now_utc) else EST_OFFSET
            
            # Build target time in ET
            target_et = datetime(
                now.year, now.month, now.day,
                int(target_hour), target_minute, 0
            )
            # Convert target ET to UTC for comparison
            target_utc = target_et - timedelta(hours=offset)
            
            delay = (target_utc - now_utc).total_seconds()
            return max(delay, 60)  # At least 1 minute from now
        else:
            # Already after 7am — reply within 15-45 minutes
            return self.rng.uniform(900, 2700)


# ---------------------------------------------------------------------------
# Example usage
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print("=" * 60)
    print("TimingEngine Demo")
    print("=" * 60)
    
    # Create engine with optional seed for reproducibility
    engine = TimingEngine(seed=42)
    
    # Demo 1: Different message types
    test_messages = [
        ("ok thanks", {"avg_response_time": 30, "message_count": 5}, {"total_messages": 5}),
        ("How much is the Submariner?", {"avg_response_time": 120, "message_count": 3}, {"total_messages": 3}),
        ("What movement does the Daytona use? Is it a clone or a modified 7750?", {"avg_response_time": 600, "message_count": 2}, {"total_messages": 2}),
        ("Hey, interested in watches", {}, {"total_messages": 0, "is_first_message": True}),
    ]
    
    print("\n--- Response Delay Examples ---")
    for msg, history, context in test_messages:
        delay = engine.calculate_delay(msg, history, context)
        typing_time = engine.get_typing_time("Thanks for your message! Let me check on that for you and get back to you shortly.")
        print(f"  Message: {msg[:50]:50s} -> delay={delay:7.1f}s, typing={typing_time:5.1f}s")
    
    # Demo 2: Time of day impact
    print("\n--- Time of Day Impact ---")
    print(f"  Current ET hour: {current_hour_et()}")
    print(f"  Is offline hours: {is_offline_hours()}")
    print(f"  Is peak hours: {is_peak_human_hours()}")
    print(f"  Is late hours: {is_late_hours()}")
    
    # Demo 3: Auto-reply
    print("\n--- Auto-Reply Check ---")
    # We'll force a check even if not offline (just for demo)
    auto_msg = engine.get_auto_reply_message()
    print(f"  Example auto-reply: {auto_msg}")
    
    # Demo 4: Busy period
    print("\n--- Busy Period Check ---")
    is_busy = engine.busy_tracker.is_busy_now()
    print(f"  Is Alex busy right now: {is_busy}")
    
    # Demo 5: Typing time variations
    print("\n--- Typing Time Variations ---")
    test_texts = [
        "Got it!",
        "The Submariner with the 3135 movement is our most popular model. It's got great weight and the finishing is excellent for the price.",
        "Hey Mike! Good to hear from you again. Last time we were talking about the Datejust 41mm, right? I actually just got a new batch in from Clean Factory — the bezel is much improved. Want me to send you some photos?",
    ]
    for text in test_texts:
        tt = engine.get_typing_time(text)
        words = len(text.split())
        print(f"  {words:3d} words: '{text[:60]}...' -> typing={tt:5.1f}s")
    
    print("\n✅ TimingEngine ready for integration.")
