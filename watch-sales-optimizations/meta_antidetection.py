"""
meta_antidetection.py — WhatsApp Anti-Detection Rules Engine
============================================================

Critical rules to make Alex's WhatsApp account behave indistinguishably 
from a real human and avoid Meta's anti-automation detection.

Key anti-detection strategies:
  1. Strategic non-reply rate: 2-5% of non-urgent messages go unanswered
  2. Variable active hours: Alex doesn't start at the same time every day
  3. Simulated typing: Message send timing based on content length
  4. Batched reply staggering: Multiple simultaneous customers get staggered
  5. Media ratio randomization: Natural photo usage patterns
  6. "Alex was here" traces: Occasional human-behavior signals
  7. Activity pattern randomization: Daily variations in online behavior
  8. Read receipt simulation: Messages aren't marked "read" instantly
  9. Conversation threading delays: Natural topic-switching pauses
  10. Day-of-week pattern variation: Weekends vs weekdays behavior

Usage:
    from meta_antidetection import AntiDetectionEngine, ActivityProfile
    
    engine = AntiDetectionEngine(seed=42)
    
    # Check if we should reply to this message
    if engine.should_reply(message_text, "cust_001"):
        delay = engine.calculate_typing_time(message_response)
        # wait for delay seconds, then send
    
    # Get today's active start time
    start_hour = engine.get_activity_start_hour()
    print(f"Alex should start today at {start_hour}:00")
"""

import random
import json
import re
import math
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any, List, Set, Tuple


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Messages that are safe to ignore (non-urgent, low-engagement)
IGNORABLE_MESSAGES = [
    "ok", "okay", "k", "kk", "k.", "ok.",
    "thanks", "thx", "ty", "thank you",
    "cool", "nice", "👍", "✅", "🙏", "😊", "❤️", "🔥", "🎉",
    "got it", "gotcha",
    "sure", "yep", "yeah",
    "no problem",
    "works", "perfect",
    "lol", "lmao", "😂", "🤣",
    "sounds good", "that works",
    "sweet", "awesome",
    "alright", "aight",
    "cool thanks", "ok thanks",
    "tyvm", "tysm",
    "gm", "gn",
]

# Media messages (just sharing photos/videos without text)
MEDIA_ONLY_PATTERNS = [
    r'^$',                    # Empty or just media
    r'^https?://\S+$',       # Just a URL
    r'^<media.*>$',           # Media placeholder
]

# Daily active hours variability (possible start/end times in ET)
POSSIBLE_START_HOURS = list(range(8, 12))      # 8am - 11am
POSSIBLE_END_HOURS = list(range(21, 24))       # 9pm - 11pm

# Weekend adjustments
WEEKEND_START_OFFSET = [0, 1, 2]   # Start 0-2 hours later on weekends
WEEKEND_END_OFFSET = [0, -1]       # End 0-1 hours earlier on weekends

# Number of "Alex was here" traces to leave per week
TRACES_PER_WEEK_MIN = 2
TRACES_PER_WEEK_MAX = 5

# ---------------------------------------------------------------------------
# Activity Profile
# ---------------------------------------------------------------------------

class ActivityProfile:
    """Daily activity profile for Alex.
    
    Tracks the day's active hours, break periods, and behavior parameters.
    Varies each day to avoid consistent patterns.
    
    Args:
        seed: Optional random seed
    """
    
    def __init__(self, seed: Optional[int] = None):
        self.rng = random.Random(seed)
        self._today_date: Optional[str] = None
        self._profile: Optional[Dict[str, Any]] = None
    
    def _get_today(self) -> str:
        """Get today's date string."""
        return datetime.now(timezone.utc).strftime('%Y-%m-%d')
    
    def _is_weekend(self) -> bool:
        """Check if today is a weekend day."""
        return datetime.now(timezone.utc).weekday() >= 5  # 5=Saturday, 6=Sunday
    
    def _generate_profile(self) -> Dict[str, Any]:
        """Generate today's activity profile."""
        is_weekend = self._is_weekend()
        
        # Base active hours
        start_hour = self.rng.choice(POSSIBLE_START_HOURS)
        end_hour = self.rng.choice(POSSIBLE_END_HOURS)
        
        # Weekend adjustments
        if is_weekend:
            start_hour += self.rng.choice(WEEKEND_START_OFFSET)
            end_hour += self.rng.choice(WEEKEND_END_OFFSET)
        
        # Clamp to valid range
        start_hour = max(7, min(start_hour, 13))
        end_hour = max(20, min(end_hour, 23))
        
        # Active intensity (how quickly Alex replies on a scale of 0.0-1.0)
        # Higher = faster replies (more "in the zone")
        active_intensity = self.rng.uniform(0.5, 1.0)
        
        # Laziness factor (some days Alex is just slower for no reason)
        laziness_factor = self.rng.uniform(0.0, 0.3) if not is_weekend else self.rng.uniform(0.1, 0.5)
        
        # Break periods (times when Alex is "away from desk")
        break_periods = []
        if self.rng.random() < 0.7:  # 70% chance of a lunch break
            lunch_start = self.rng.randint(11, 13)
            lunch_duration = self.rng.randint(20, 60)  # 20-60 minutes
            break_periods.append({
                'start': lunch_start,
                'duration_minutes': lunch_duration,
                'reason': 'lunch',
            })
        
        if self.rng.random() < 0.4:  # 40% chance of an afternoon break
            break_start = self.rng.randint(14, 16)
            break_duration = self.rng.randint(10, 30)  # 10-30 minutes
            break_periods.append({
                'start': break_start,
                'duration_minutes': break_duration,
                'reason': 'break',
            })
        
        # Reply rate (what % of messages get a reply today)
        # Varies 95-100% normally, can dip to 90% on lazy days
        base_reply_rate = 0.97 - (laziness_factor * 0.1)
        reply_rate = max(0.90, min(1.0, base_reply_rate))
        
        # Media probability (chance of including a photo in responses)
        media_probability = self.rng.uniform(0.15, 0.35)
        
        # Typing speed multiplier (some days Alex types faster/slower)
        typing_speed_mult = self.rng.uniform(0.8, 1.3)
        
        return {
            'date': self._get_today(),
            'is_weekend': is_weekend,
            'start_hour': start_hour,
            'end_hour': end_hour,
            'active_intensity': round(active_intensity, 2),
            'laziness_factor': round(laziness_factor, 2),
            'break_periods': break_periods,
            'reply_rate': round(reply_rate, 3),
            'media_probability': round(media_probability, 2),
            'typing_speed_mult': round(typing_speed_mult, 2),
        }
    
    def get_profile(self) -> Dict[str, Any]:
        """Get today's activity profile, generating it if needed."""
        today = self._get_today()
        if self._profile is None or self._profile['date'] != today:
            self._profile = self._generate_profile()
        return self._profile
    
    def get_start_hour(self) -> int:
        """Get today's active start hour (ET)."""
        return self.get_profile()['start_hour']
    
    def get_end_hour(self) -> int:
        """Get today's active end hour (ET)."""
        return self.get_profile()['end_hour']
    
    def get_active_intensity(self) -> float:
        """Get today's active intensity (0.0-1.0)."""
        return self.get_profile()['active_intensity']
    
    def get_reply_rate(self) -> float:
        """Get today's reply rate (0.0-1.0)."""
        return self.get_profile()['reply_rate']
    
    def get_media_probability(self) -> float:
        """Get today's probability of sending media."""
        return self.get_profile()['media_probability']
    
    def get_typing_speed_mult(self) -> float:
        """Get today's typing speed multiplier."""
        return self.get_profile()['typing_speed_mult']
    
    def is_on_break(self, hour: int, minute: int) -> bool:
        """Check if Alex is currently on a break."""
        profile = self.get_profile()
        for break_period in profile['break_periods']:
            break_start = break_period['start']
            break_end = break_start + (break_period['duration_minutes'] / 60)
            current_time = hour + (minute / 60)
            if break_start <= current_time < break_end:
                return True
        return False
    
    def is_active(self, hour: int) -> bool:
        """Check if Alex is active at this hour."""
        profile = self.get_profile()
        return profile['start_hour'] <= hour < profile['end_hour']


# ---------------------------------------------------------------------------
# Typing simulation
# ---------------------------------------------------------------------------

def calculate_typing_duration(
    text: str,
    speed_mult: float = 1.0,
    rng: Optional[random.Random] = None,
) -> float:
    """Calculate a realistic typing duration for a message.
    
    Returns seconds (float) that represents how long Alex appears to be typing.
    
    Args:
        text: The message text
        speed_mult: Multiplier for typing speed (0.8 = slower, 1.2 = faster)
        rng: Random number generator
    
    Returns:
        Typing duration in seconds
    """
    if rng is None:
        rng = random.Random()
    
    word_count = len(text.split())
    char_count = len(text)
    
    # Base typing speed: ~40 WPM with variation
    # But includes thinking pauses
    if word_count <= 3:
        # Quick reply
        base = rng.uniform(1.5, 5.0)
    elif word_count <= 10:
        # Short message
        base = rng.uniform(3.0, 10.0)
    elif word_count <= 25:
        # Medium message
        base = rng.uniform(8.0, 22.0)
    elif word_count <= 50:
        # Long message
        base = rng.uniform(18.0, 38.0)
    else:
        # Very long message
        base = rng.uniform(30.0, 60.0)
    
    # Add thinking pauses for longer messages
    if word_count > 15 and rng.random() < 0.25:
        base += rng.uniform(2.0, 6.0)
    if word_count > 30 and rng.random() < 0.3:
        base += rng.uniform(3.0, 8.0)
    
    # Apply speed multiplier
    base *= speed_mult
    
    # Add small random jitter
    base *= rng.uniform(0.9, 1.1)
    
    return round(base, 1)


# ---------------------------------------------------------------------------
# Main AntiDetectionEngine
# ---------------------------------------------------------------------------

class AntiDetectionEngine:
    """Anti-detection rules engine for WhatsApp automation.
    
    Ensures Alex's behavior is indistinguishable from a human to avoid
    Meta's anti-automation systems.
    
    Features:
    - Strategic non-reply rate (2-5% of messages ignored)
    - Variable daily active hours
    - Batched reply staggering
    - Media ratio randomization
    - "Alex was here" trace signals
    - Activity pattern randomization
    - Per-customer message tracking for natural pacing
    
    Args:
        seed: Optional random seed for deterministic testing
        state_path: Optional path to persist state
    """
    
    def __init__(self, seed: Optional[int] = None, state_path: Optional[str] = None):
        self.rng = random.Random(seed)
        self.profile = ActivityProfile(seed=self.rng.randint(0, 2**31) if seed is None else seed + 1)
        self.state_path = state_path
        
        # Track reply decisions per customer (message_id -> replied bool)
        self._reply_decisions: Dict[str, bool] = {}
        
        # Track batched replies to avoid instant-multi-reply patterns
        self._batched_reply_times: List[datetime] = []
        
        # Track "Alex was here" traces for the week
        self._weekly_traces: int = 0
        self._last_trace_week: int = -1
        
        # Track ignored messages per customer
        self._ignored_counts: Dict[str, int] = {}
        
        # Track last reply time per customer for natural spacing
        self._last_reply_time: Dict[str, datetime] = {}
        
        # Track media sent per customer
        self._media_sent: Dict[str, int] = {}
    
    # -----------------------------------------------------------------------
    # Rule 1: Strategic non-reply (2-5% of messages unanswered)
    # -----------------------------------------------------------------------
    
    def should_reply(
        self,
        message: str,
        customer_id: str,
        is_urgent: bool = False,
    ) -> bool:
        """Determine if Alex should reply to this message.
        
        NEVER reply to 100% of messages. Strategically "miss" some:
        - 2-5% of all messages go unanswered
        - ~30% of ignorable messages (ok, thanks, 👍) go unanswered
        - Urgent messages always get a reply
        - First message from a customer always gets a reply
        - Angry customers always get a reply
        
        Args:
            message: The customer's message text
            customer_id: Customer identifier
            is_urgent: Whether the message is marked urgent
        
        Returns:
            True if Alex should reply, False to strategically ignore
        """
        # Always reply to urgent messages
        if is_urgent:
            return True
        
        # Always reply to first messages in a conversation
        if customer_id not in self._last_reply_time:
            return True
        
        msg_lower = message.lower().strip()
        
        # Check if this is an ignorable message
        is_ignorable = False
        for ignorable in IGNORABLE_MESSAGES:
            if msg_lower == ignorable or msg_lower.startswith(ignorable):
                is_ignorable = True
                break
        
        if is_ignorable:
            # ~30% chance to ignore simple acknowledgments
            return self.rng.random() >= 0.30
        
        # General non-reply rate: 2-5% based on today's profile
        reply_rate = self.profile.get_reply_rate()
        should_reply = self.rng.random() < reply_rate
        
        if not should_reply:
            # Track the ignored message
            self._ignored_counts[customer_id] = self._ignored_counts.get(customer_id, 0) + 1
        
        return should_reply
    
    def get_ignore_rate(self, customer_id: str) -> float:
        """Get the current ignore rate for a customer."""
        total = self._ignored_counts.get(customer_id, 0)
        if total == 0:
            return 0.0
        # This is an approximation since we don't track total messages here
        return min(total / 50, 0.1)  # Cap at 10%
    
    # -----------------------------------------------------------------------
    # Rule 2: Variable active hours
    # -----------------------------------------------------------------------
    
    def get_activity_start_hour(self) -> int:
        """Get today's active start hour in ET.
        
        Alex should not start at the same time every day.
        Some days start at 8am, some at 9am, some at 10am.
        """
        return self.profile.get_start_hour()
    
    def get_activity_end_hour(self) -> int:
        """Get today's active end hour in ET."""
        return self.profile.get_end_hour()
    
    def is_online_now(self) -> bool:
        """Check if Alex should appear online right now.
        
        Factors:
        - Current hour vs today's active hours
        - Break periods
        - Random "offline" moments (10% chance during active hours)
        """
        now = datetime.now(timezone.utc)
        # We need ET time
        from timing_engine import current_hour_et, current_minute_et
        
        hour = current_hour_et()
        minute = current_minute_et()
        
        if not self.profile.is_active(hour):
            return False
        
        if self.profile.is_on_break(hour, minute):
            return False
        
        # 10% chance of being "offline" even during active hours
        if self.rng.random() < 0.1:
            return False
        
        return True
    
    def get_daily_active_hours(self) -> Tuple[int, int]:
        """Get today's active hour range as (start, end)."""
        return (self.profile.get_start_hour(), self.profile.get_end_hour())
    
    # -----------------------------------------------------------------------
    # Rule 3: Typing simulation
    # -----------------------------------------------------------------------
    
    def calculate_typing_time(self, message: str) -> float:
        """Calculate how long Alex should appear to be typing.
        
        Short message (1-3 words): 3-8 seconds
        Long message (15+ words): 15-40 seconds
        Includes day-specific speed variation.
        """
        speed_mult = self.profile.get_typing_speed_mult()
        return calculate_typing_duration(message, speed_mult, self.rng)
    
    # -----------------------------------------------------------------------
    # Rule 4: Batched reply staggering
    # -----------------------------------------------------------------------
    
    def get_reply_delay_for_batch(
        self,
        customer_id: str,
        conversation_count: Optional[int] = None,
    ) -> float:
        """Calculate delay when multiple customers message at the same time.
        
        If 3 customers message within 2 minutes, don't reply to all 3 instantly.
        Stagger them with 2-5 minute gaps.
        
        Args:
            customer_id: Customer identifier
            conversation_count: Number of active conversations (optional)
        
        Returns:
            Additional delay in seconds
        """
        now = datetime.now(timezone.utc)
        
        # Clean old entries (older than 5 minutes)
        self._batched_reply_times = [
            t for t in self._batched_reply_times
            if (now - t).total_seconds() < 300
        ]
        
        if not self._batched_reply_times:
            # First reply in this batch window — no extra delay
            self._batched_reply_times.append(now)
            return 0.0
        
        # Check how many recent replies we've sent
        recent_count = len(self._batched_reply_times)
        
        if recent_count >= 2:
            # We've already replied to 2+ people recently — stagger
            delay = self.rng.uniform(120, 300)  # 2-5 minutes
        elif recent_count >= 1:
            # One person already got a reply — slight delay
            delay = self.rng.uniform(30, 120)  # 30s - 2min
        else:
            delay = 0.0
        
        # Check if we JUST replied to this customer
        last_reply = self._last_reply_time.get(customer_id)
        if last_reply and (now - last_reply).total_seconds() < 60:
            # Just replied to this customer — wait before next
            delay = max(delay, self.rng.uniform(30, 120))
        
        self._batched_reply_times.append(now)
        return delay
    
    # -----------------------------------------------------------------------
    # Rule 5: Media ratio randomization
    # -----------------------------------------------------------------------
    
    def should_send_media(self, customer_id: str) -> bool:
        """Determine if Alex should include media in the next response.
        
        Some conversations get lots of photos, some get none.
        Varies naturally based on:
        - Today's media probability setting
        - How many photos already sent to this customer
        - Random variation
        """
        prob = self.profile.get_media_probability()
        
        # Reduce probability if we've already sent a lot to this customer
        media_count = self._media_sent.get(customer_id, 0)
        if media_count >= 5:
            prob *= 0.5
        if media_count >= 10:
            prob *= 0.3
        
        return self.rng.random() < prob
    
    def mark_media_sent(self, customer_id: str):
        """Record that media was sent to a customer."""
        self._media_sent[customer_id] = self._media_sent.get(customer_id, 0) + 1
    
    # -----------------------------------------------------------------------
    # Rule 6: "Alex was here" traces
    # -----------------------------------------------------------------------
    
    def should_leave_trace(self) -> bool:
        """Determine if Alex should leave a 'was here' trace.
        
        These are messages that show human behavior patterns:
        - Sending a message at 2:47 PM on a Tuesday
        - Replying from a different time zone
        - Showing "active" status inconsistently
        
        Returns:
            True if a trace signal should be emitted
        """
        now = datetime.now(timezone.utc)
        current_week = now.isocalendar()[1]
        
        # Reset weekly counter
        if current_week != self._last_trace_week:
            self._weekly_traces = 0
            self._last_trace_week = current_week
        
        if self._weekly_traces >= TRACES_PER_WEEK_MAX:
            return False
        
        # Random chance to leave a trace (increases when we haven't left many)
        if self._weekly_traces < TRACES_PER_WEEK_MIN:
            # Need to leave more traces
            chance = 0.1
        else:
            # Normal rate
            chance = 0.02
        
        if self.rng.random() < chance:
            self._weekly_traces += 1
            return True
        
        return False
    
    def get_trace_message(self) -> str:
        """Get a trace message that shows human behavior."""
        traces = [
            # Off-hours check
            "Hey, just saw this. I'm actually out right now but wanted to reply so I don't forget. I'll get back to you properly in a bit!",
            # Multi-tasking signal
            "Sorry for the slow reply — been running around all day. Let me look at your message now.",
            # Late night
            "Haha can't sleep so I'm going through messages. Glad I caught yours!",
            # Morning signal
            "Morning! Just getting to my messages from last night.",
            # Inconsistent timing
            "Just got back to my desk. Let me check on that for you.",
            # Weekend signal
            "Hey! Sorry, taking it easy today so replies might be a bit slow.",
            # Eating signal
            "Grabbing lunch real quick but wanted to reply so you know I saw this.",
            # Busy signal
            "In the middle of something but wanted to get back to you quick — more details soon.",
            # Device switch signal
            "Switched to my computer so I can type this out properly lol.",
            # Real-world interruption
            "Sorry, got pulled away. Let me pick this back up.",
        ]
        return self.rng.choice(traces)
    
    def get_trace_count_for_week(self) -> int:
        """Get how many traces have been left this week."""
        return self._weekly_traces
    
    # -----------------------------------------------------------------------
    # Rule 7: Read receipt simulation
    # -----------------------------------------------------------------------
    
    def should_mark_read(self, message_time: Optional[datetime] = None) -> bool:
        """Determine if Alex should have 'read' the message.
        
        Real humans don't instantly read messages. Sometimes they let them sit.
        - 30% chance: message is "read" within 1-5 minutes
        - 50% chance: message is "read" within 5-30 minutes
        - 15% chance: message is "read" within 30-120 minutes
        - 5% chance: message is never "marked read" (left on read)
        """
        roll = self.rng.random()
        if roll < 0.3:
            return True  # Quick read
        elif roll < 0.8:
            return True  # Normal read
        elif roll < 0.95:
            return True  # Slow read
        else:
            return False  # Left on read
    
    def get_read_delay(self) -> float:
        """Get the delay before marking a message as read.
        
        Returns seconds before mark-read happens.
        """
        roll = self.rng.random()
        if roll < 0.3:
            # Quick see
            return self.rng.uniform(5, 60)
        elif roll < 0.8:
            # Normal
            return self.rng.uniform(60, 300)
        elif roll < 0.95:
            # Slow
            return self.rng.uniform(300, 1200)
        else:
            # Very slow or never
            return self.rng.uniform(1200, 3600)
    
    # -----------------------------------------------------------------------
    # Rule 8: Activity rhythm / pulse
    # -----------------------------------------------------------------------
    
    def get_activity_pulse(self) -> Dict[str, Any]:
        """Get Alex's current activity rhythm.
        
        Simulates natural human patterns:
        - Peak activity in late morning (10-12) 
        - Dip during lunch (12-1)
        - Peak again in afternoon (2-4)
        - Evening activity (7-10) but more relaxed
        """
        from timing_engine import current_hour_et
        
        hour = current_hour_et()
        
        # Activity intensity by hour (0.0 = offline, 1.0 = very active)
        if 10 <= hour <= 12:
            intensity = 0.9  # Morning peak
        elif 14 <= hour <= 16:
            intensity = 0.85  # Afternoon peak
        elif 19 <= hour <= 22:
            intensity = 0.7  # Evening (more relaxed)
        elif 7 <= hour < 10:
            intensity = 0.5  # Morning warmup
        elif 12 <= hour < 14:
            intensity = 0.4  # Lunch dip
        elif 22 <= hour < 24:
            intensity = 0.3  # Winding down
        elif 0 <= hour < 7:
            intensity = 0.05  # Sleeping
        else:
            intensity = 0.2
        
        # Apply today's intensity modifier
        intensity *= self.profile.get_active_intensity()
        intensity = min(1.0, max(0.0, intensity))
        
        # Expected response time based on intensity
        if intensity > 0.8:
            expected_response = "within 5-15 minutes"
        elif intensity > 0.6:
            expected_response = "within 15-45 minutes"
        elif intensity > 0.4:
            expected_response = "within 30-90 minutes"
        elif intensity > 0.2:
            expected_response = "within 1-4 hours"
        else:
            expected_response = "next active period"
        
        return {
            'hour': hour,
            'intensity': round(intensity, 2),
            'expected_response': expected_response,
            'is_on_break': self.profile.is_on_break(hour, datetime.now(timezone.utc).minute),
            'active_range': self.get_daily_active_hours(),
        }
    
    # -----------------------------------------------------------------------
    # Combined decision engine
    # -----------------------------------------------------------------------
    
    def get_response_plan(
        self,
        message: str,
        customer_id: str,
        is_urgent: bool = False,
        conversation_count: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Get a complete response plan for a customer message.
        
        This is the main entry point for the anti-detection engine.
        It combines all rules into a single decision:
        - Whether to reply at all
        - How long to wait before replying
        - How long to simulate typing
        - Whether to include media
        - Whether to leave a trace
        
        Args:
            message: The customer's message text
            customer_id: Customer identifier
            is_urgent: Whether the message is urgent
            conversation_count: Number of active conversations
        
        Returns:
            Dict with:
            - should_reply (bool)
            - total_delay_seconds (float)
            - typing_seconds (float)
            - include_media (bool)
            - leave_trace (bool)
            - trace_message (str or None)
            - batch_delay (float)
            - read_delay (float)
            - active_intensity (float)
        """
        # Rule 1: Should we reply at all?
        reply = self.should_reply(message, customer_id, is_urgent)
        
        if not reply:
            return {
                'should_reply': False,
                'total_delay_seconds': 0,
                'typing_seconds': 0,
                'include_media': False,
                'leave_trace': False,
                'trace_message': None,
                'batch_delay': 0,
                'read_delay': 0,
                'active_intensity': self.get_activity_pulse()['intensity'],
            }
        
        # Rule 5: Should we include media?
        include_media = self.should_send_media(customer_id)
        
        # Rule 6: Should we leave a trace?
        leave_trace = self.should_leave_trace()
        trace_message = self.get_trace_message() if leave_trace else None
        
        # Rule 4: Batch staggering
        batch_delay = self.get_reply_delay_for_batch(customer_id, conversation_count)
        
        # Rule 7: Read receipt timing
        # Only calculate if we haven't already marked read
        now = datetime.now(timezone.utc)
        last_reply = self._last_reply_time.get(customer_id)
        if last_reply and (now - last_reply).total_seconds() < 60:
            read_delay = 0  # Already "seen" recently
        else:
            read_delay = self.get_read_delay() if self.should_mark_read() else 0
        
        # Rule 3: Typing simulation
        typing_seconds = 0
        
        # Total delay
        total_delay = batch_delay
        
        # Update state
        self._last_reply_time[customer_id] = datetime.now(timezone.utc)
        
        return {
            'should_reply': True,
            'total_delay_seconds': round(total_delay, 1),
            'typing_seconds': typing_seconds,
            'include_media': include_media,
            'leave_trace': leave_trace,
            'trace_message': trace_message,
            'batch_delay': round(batch_delay, 1),
            'read_delay': round(read_delay, 1),
            'active_intensity': self.get_activity_pulse()['intensity'],
        }
    
    def record_reply_sent(self, customer_id: str):
        """Record that a reply was sent to a customer."""
        self._last_reply_time[customer_id] = datetime.now(timezone.utc)
    
    def get_stats(self) -> Dict[str, Any]:
        """Get current anti-detection statistics."""
        profile = self.profile.get_profile()
        pulse = self.get_activity_pulse()
        
        return {
            'today': profile['date'],
            'is_weekend': profile['is_weekend'],
            'active_hours': f"{profile['start_hour']}:00-{profile['end_hour']}:00",
            'reply_rate': profile['reply_rate'],
            'active_intensity': profile['active_intensity'],
            'current_intensity': pulse['intensity'],
            'media_probability': profile['media_probability'],
            'typing_speed': profile['typing_speed_mult'],
            'breaks_today': len(profile['break_periods']),
            'weekly_traces': self._weekly_traces,
            'total_customers_tracked': len(self._last_reply_time),
        }


# ---------------------------------------------------------------------------
# Example usage
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print("=" * 60)
    print("AntiDetectionEngine Demo")
    print("=" * 60)
    
    engine = AntiDetectionEngine(seed=42)
    
    # --- Activity profile ---
    print("\n--- Today's Activity Profile ---")
    profile = engine.profile.get_profile()
    print(f"  Date: {profile['date']}")
    print(f"  Weekend: {profile['is_weekend']}")
    print(f"  Active hours: {profile['start_hour']}:00 - {profile['end_hour']}:00")
    print(f"  Active intensity: {profile['active_intensity']}")
    print(f"  Laziness factor: {profile['laziness_factor']}")
    print(f"  Reply rate: {profile['reply_rate']}")
    print(f"  Media probability: {profile['media_probability']}")
    print(f"  Typing speed: {profile['typing_speed_mult']}x")
    print(f"  Breaks: {profile['break_periods']}")
    
    # --- Strategic non-reply ---
    print("\n--- Strategic Non-Reply Decisions ---")
    test_messages = [
        ("ok thanks", "cust_001", False),
        ("How much is the Submariner?", "cust_001", False),
        ("I want a refund!", "cust_001", True),  # urgent
        ("👍", "cust_002", False),
        ("Hey, interested in watches", "cust_003", False),
    ]
    
    for msg, cid, urgent in test_messages:
        decision = engine.should_reply(msg, cid, urgent)
        print(f"  Reply? {decision:5} | Urgent? {urgent} | \"{msg[:40]:40s}\" (cust: {cid})")
    
    # --- Typing time simulation ---
    print("\n--- Typing Time Simulation ---")
    test_texts = [
        "Got it!",
        "The Submariner with the VS3235 movement is $488 shipped. It's our most popular model.",
        "Hey Mike! Long time no chat! Last time we were talking about the Daytona. I actually just got some new photos from Clean Factory — the bezel is much improved on this batch. Want me to send them over?",
    ]
    for text in test_texts:
        tt = engine.calculate_typing_time(text)
        words = len(text.split())
        print(f"  {words:3d} words ({len(text):3d} chars): typing={tt:5.1f}s")
    
    # --- Batch staggering ---
    print("\n--- Batch Staggering ---")
    for i in range(5):
        delay = engine.get_reply_delay_for_batch(f"cust_{i:03d}")
        print(f"  Customer {i}: batch_delay={delay:5.1f}s")
    
    # --- Response plan ---
    print("\n--- Complete Response Plan ---")
    plan = engine.get_response_plan(
        "How much is the Clean Factory Daytona?",
        "cust_005",
        is_urgent=False,
        conversation_count=3,
    )
    for key, value in plan.items():
        print(f"  {key}: {value}")
    
    # --- Activity pulse ---
    print("\n--- Activity Pulse ---")
    pulse = engine.get_activity_pulse()
    for key, value in pulse.items():
        print(f"  {key}: {value}")
    
    # --- Stats ---
    print("\n--- Engine Stats ---")
    stats = engine.get_stats()
    for key, value in stats.items():
        print(f"  {key}: {value}")
    
    # --- Trace messages ---
    print("\n--- Trace Messages ---")
    if engine.should_leave_trace():
        print(f"  \"{engine.get_trace_message()}\"")
    
    # --- Read receipt simulation ---
    print("\n--- Read Receipt Simulation ---")
    for _ in range(5):
        mark_read = engine.should_mark_read()
        delay = engine.get_read_delay() if mark_read else 0
        print(f"  Mark read: {mark_read:5} | delay: {delay:7.1f}s")
    
    print("\n✅ AntiDetectionEngine ready for integration.")
