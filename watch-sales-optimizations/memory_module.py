"""
memory_module.py — Customer Memory System
==========================================

Lightweight SQLite-based memory system for tracking customer history,
preferences, personal details, and conversation patterns across sessions.

Features:
  - Persistent SQLite storage (no external DB required)
  - Remember returning customers with personal references
  - Track discussed models, interests, objections
  - Emotional trajectory analysis
  - Strategy recommendations based on history
  - JSON fields for flexible data storage
  - Thread-safe with connection pooling

Schema:
  customer_memories:
    - customer_id (TEXT PRIMARY KEY)
    - first_name (TEXT)
    - last_seen (TIMESTAMP)
    - total_conversations (INTEGER)
    - discussed_models (TEXT JSON array)
    - interests (TEXT JSON)
    - personality_notes (TEXT)
    - last_model_of_interest (TEXT)
    - price_comfort_zone (TEXT)
    - objection_history (TEXT JSON)
    - personal_details (TEXT JSON)
    - custom_notes (TEXT)
    
  conversation_log:
    - id (INTEGER PRIMARY KEY AUTOINCREMENT)
    - customer_id (TEXT)
    - timestamp (TIMESTAMP)
    - message_type (TEXT: 'sent' | 'received')
    - message_content (TEXT)
    - sentiment (TEXT: 'positive' | 'neutral' | 'negative' | 'angry')
    - topic (TEXT)
    
  emotional_trajectory:
    - id (INTEGER PRIMARY KEY AUTOINCREMENT)
    - customer_id (TEXT)
    - conversation_number (INTEGER)
    - overall_sentiment (TEXT)
    - price_sensitivity (REAL 0.0-1.0)
    - urgency (REAL 0.0-1.0)
    - key_objections (TEXT JSON)
    - notes (TEXT)

Usage:
    from memory_module import CustomerMemory

    mem = CustomerMemory(db_path="customer_memories.db")
    
    # Save a memory
    mem.save_customer("cust_123", first_name="Mike", last_model="Submariner")
    
    # Retrieve memory
    customer = mem.get_customer("cust_123")
    if customer:
        greeting = mem.generate_returning_greeting("cust_123")
        print(greeting)
    
    # Log a conversation message
    mem.log_message("cust_123", "received", "How much is the Daytona?", sentiment="neutral")
    
    # Get strategy recommendation
    strategy = mem.get_strategy_recommendation("cust_123")
    print(strategy)
"""

import sqlite3
import json
import os
import threading
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List, Tuple


# ---------------------------------------------------------------------------
# Database schema
# ---------------------------------------------------------------------------

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS customer_memories (
    customer_id TEXT PRIMARY KEY,
    first_name TEXT,
    last_seen TIMESTAMP,
    total_conversations INTEGER DEFAULT 1,
    discussed_models TEXT DEFAULT '[]',
    interests TEXT DEFAULT '{}',
    personality_notes TEXT DEFAULT '',
    last_model_of_interest TEXT DEFAULT '',
    price_comfort_zone TEXT DEFAULT '',
    objection_history TEXT DEFAULT '[]',
    personal_details TEXT DEFAULT '{}',
    custom_notes TEXT DEFAULT ''
);

CREATE TABLE IF NOT EXISTS conversation_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    customer_id TEXT NOT NULL,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    message_type TEXT NOT NULL CHECK(message_type IN ('sent', 'received')),
    message_content TEXT NOT NULL,
    sentiment TEXT DEFAULT 'neutral' CHECK(sentiment IN ('positive', 'neutral', 'negative', 'angry')),
    topic TEXT DEFAULT 'general',
    FOREIGN KEY (customer_id) REFERENCES customer_memories(customer_id)
);

CREATE INDEX IF NOT EXISTS idx_conversation_log_customer 
    ON conversation_log(customer_id, timestamp);

CREATE TABLE IF NOT EXISTS emotional_trajectory (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    customer_id TEXT NOT NULL,
    conversation_number INTEGER NOT NULL,
    overall_sentiment TEXT DEFAULT 'neutral',
    price_sensitivity REAL DEFAULT 0.5,
    urgency REAL DEFAULT 0.5,
    key_objections TEXT DEFAULT '[]',
    notes TEXT DEFAULT '',
    FOREIGN KEY (customer_id) REFERENCES customer_memories(customer_id)
);

CREATE INDEX IF NOT EXISTS idx_emotional_trajectory_customer 
    ON emotional_trajectory(customer_id, conversation_number);
"""


# ---------------------------------------------------------------------------
# Retuning greeting templates
# ---------------------------------------------------------------------------

RETURNING_GREETINGS_WITH_NAME = [
    "Hey {name}! Good to hear from you again!",
    "{name}! Good to see you pop back in!",
    "Hey {name}, was wondering when you'd come back!",
    "{name}! Long time no chat. How's everything?",
    "There you are, {name}! Was just thinking about watches.",
    "Hey {name}, welcome back!",
    "{name}! Hope you've been well. What's on your mind?",
    "Good to see you again, {name}! Still thinking about that watch?",
]

RETURNING_GREETINGS_WITH_MODEL = [
    "Good to hear from you! Last time we were talking about the {model} — still on your mind?",
    "Hey! We were chatting about the {model} last time. Any more questions on it?",
    "Welcome back! Still thinking about that {model}?",
    "Good timing — I just got some new {model} photos if you're still interested!",
]

RETURNING_GREETINGS_NAME_MODEL = [
    "Hey {name}! Good to hear from you again. Last time we were talking about the {model} — still interested?",
    "{name}! We were chatting about the {model} last time. Want to pick up where we left off?",
    "Hey {name}! Was just thinking — you were asking about the {model}. Still on your radar?",
    "{name}, good to see you! Still looking at that {model} or something new catch your eye?",
]

RETURNING_GREETINGS_WITH_DETAIL = [
    "Hey {name}! How's {city} treating you? Still thinking about watches?",
    "{name}! Good to see you. How's everything with {detail}?",
    "Hey {name}! Did you end up checking out that {model} like we talked about?",
]

FIRST_TIME_GREETINGS = [
    "Hey! Thanks for reaching out. What can I help you with?",
    "Hey there! Welcome. Looking for anything specific?",
    "Hey! Welcome. I'm Alex — feel free to ask me anything about watches.",
    "Thanks for messaging! What kind of watch are you looking for?",
    "Hey! What brings you by? Looking for something specific?",
]


# ---------------------------------------------------------------------------
# Main CustomerMemory class
# ---------------------------------------------------------------------------

class CustomerMemory:
    """SQLite-based persistent memory system for customer tracking.
    
    Thread-safe. Creates database and tables on init if they don't exist.
    
    Args:
        db_path: Path to SQLite database file (default: 'customer_memories.db')
        auto_commit: Whether to auto-commit after each write (default: True)
    """
    
    def __init__(self, db_path: str = "customer_memories.db", auto_commit: bool = True):
        self.db_path = db_path
        self.auto_commit = auto_commit
        self._local = threading.local()
        self._init_db()
    
    def _get_connection(self) -> sqlite3.Connection:
        """Get a thread-local database connection."""
        if not hasattr(self._local, 'connection') or self._local.connection is None:
            self._local.connection = sqlite3.connect(self.db_path)
            self._local.connection.row_factory = sqlite3.Row
            self._local.connection.execute("PRAGMA journal_mode=WAL")
            self._local.connection.execute("PRAGMA foreign_keys=ON")
        return self._local.connection
    
    def _init_db(self):
        """Initialize the database schema."""
        conn = self._get_connection()
        conn.executescript(SCHEMA_SQL)
        if self.auto_commit:
            conn.commit()
    
    def close(self):
        """Close the thread-local connection."""
        if hasattr(self._local, 'connection') and self._local.connection:
            self._local.connection.close()
            self._local.connection = None
    
    # -----------------------------------------------------------------------
    # Customer CRUD
    # -----------------------------------------------------------------------
    
    def save_customer(
        self,
        customer_id: str,
        first_name: Optional[str] = None,
        last_model: Optional[str] = None,
        interests: Optional[Dict[str, Any]] = None,
        personality_notes: Optional[str] = None,
        price_comfort_zone: Optional[str] = None,
        personal_details: Optional[Dict[str, Any]] = None,
        custom_notes: Optional[str] = None,
    ) -> bool:
        """Save or update customer information.
        
        If the customer already exists, merge the new data with existing data.
        
        Args:
            customer_id: Unique identifier for the customer
            first_name: Customer's first name
            last_model: Last model of interest
            interests: Dict of interests (e.g., {"hobbies": ["cycling"], "job": "engineer"})
            personality_notes: Notes about customer's personality/preferences
            price_comfort_zone: e.g., "300-500" or "500-800"
            personal_details: Dict of personal info (e.g., {"city": "NYC", "kids": 2})
            custom_notes: Free text notes
        
        Returns:
            True if successful
        """
        conn = self._get_connection()
        now = datetime.now(timezone.utc).isoformat()
        
        # Check if customer exists
        existing = self.get_customer(customer_id)
        
        if existing:
            # Merge fields
            first_name = first_name or existing.get('first_name')
            
            # Merge discussed models
            existing_models = json.loads(existing.get('discussed_models', '[]'))
            if last_model and last_model not in existing_models:
                existing_models.append(last_model)
            discussed_models = json.dumps(existing_models)
            
            # Merge interests
            existing_interests = json.loads(existing.get('interests', '{}'))
            if interests:
                existing_interests.update(interests)
            interests_json = json.dumps(existing_interests)
            
            # Merge personal details
            existing_details = json.loads(existing.get('personal_details', '{}'))
            if personal_details:
                existing_details.update(personal_details)
            personal_details_json = json.dumps(existing_details)
            
            # Merge personality notes
            existing_personality = existing.get('personality_notes', '')
            if personality_notes and personality_notes not in existing_personality:
                existing_personality += f"; {personality_notes}" if existing_personality else personality_notes
            personality_notes = existing_personality
            
            # Merge price comfort zone
            price_zone = price_comfort_zone or existing.get('price_comfort_zone', '')
            
            # Merge custom notes
            existing_notes = existing.get('custom_notes', '')
            if custom_notes and custom_notes not in existing_notes:
                existing_notes += f"\n[{now}] {custom_notes}" if existing_notes else custom_notes
            custom_notes = existing_notes
            
            last_model_of_interest = last_model or existing.get('last_model_of_interest', '')
            total_conversations = existing.get('total_conversations', 1)
            
            conn.execute("""
                UPDATE customer_memories SET
                    first_name = ?,
                    last_seen = ?,
                    total_conversations = ?,
                    discussed_models = ?,
                    interests = ?,
                    personality_notes = ?,
                    last_model_of_interest = ?,
                    price_comfort_zone = ?,
                    personal_details = ?,
                    custom_notes = ?
                WHERE customer_id = ?
            """, (
                first_name, now, total_conversations,
                discussed_models, interests_json, personality_notes,
                last_model_of_interest, price_zone,
                personal_details_json, custom_notes,
                customer_id
            ))
        else:
            # New customer
            discussed_models = json.dumps([last_model] if last_model else [])
            interests_json = json.dumps(interests or {})
            personal_details_json = json.dumps(personal_details or {})
            
            conn.execute("""
                INSERT INTO customer_memories (
                    customer_id, first_name, last_seen, total_conversations,
                    discussed_models, interests, personality_notes,
                    last_model_of_interest, price_comfort_zone,
                    personal_details, custom_notes
                ) VALUES (?, ?, ?, 1, ?, ?, ?, ?, ?, ?, ?)
            """, (
                customer_id, first_name, now,
                discussed_models, interests_json, personality_notes or '',
                last_model or '', price_comfort_zone or '',
                personal_details_json, custom_notes or ''
            ))
        
        if self.auto_commit:
            conn.commit()
        return True
    
    def get_customer(self, customer_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve customer memory by ID.
        
        Returns a dict of customer data, or None if not found.
        """
        conn = self._get_connection()
        cursor = conn.execute(
            "SELECT * FROM customer_memories WHERE customer_id = ?",
            (customer_id,)
        )
        row = cursor.fetchone()
        if row is None:
            return None
        return dict(row)
    
    def get_all_customers(self) -> List[Dict[str, Any]]:
        """Retrieve all customer memories."""
        conn = self._get_connection()
        cursor = conn.execute("SELECT * FROM customer_memories ORDER BY last_seen DESC")
        return [dict(row) for row in cursor.fetchall()]
    
    def delete_customer(self, customer_id: str) -> bool:
        """Delete a customer and all related data."""
        conn = self._get_connection()
        conn.execute("DELETE FROM conversation_log WHERE customer_id = ?", (customer_id,))
        conn.execute("DELETE FROM emotional_trajectory WHERE customer_id = ?", (customer_id,))
        conn.execute("DELETE FROM customer_memories WHERE customer_id = ?", (customer_id,))
        if self.auto_commit:
            conn.commit()
        return True
    
    def increment_conversation(self, customer_id: str) -> int:
        """Increment the conversation count for a returning customer.
        
        Returns the new conversation number.
        """
        conn = self._get_connection()
        customer = self.get_customer(customer_id)
        if customer:
            new_count = customer['total_conversations'] + 1
            conn.execute(
                "UPDATE customer_memories SET total_conversations = ?, last_seen = ? WHERE customer_id = ?",
                (new_count, datetime.now(timezone.utc).isoformat(), customer_id)
            )
            if self.auto_commit:
                conn.commit()
            return new_count
        return 1
    
    # -----------------------------------------------------------------------
    # Conversation logging
    # -----------------------------------------------------------------------
    
    def log_message(
        self,
        customer_id: str,
        message_type: str,
        message_content: str,
        sentiment: str = 'neutral',
        topic: str = 'general',
    ) -> int:
        """Log a sent or received message in the conversation log.
        
        Args:
            customer_id: Customer identifier
            message_type: 'sent' or 'received'
            message_content: The message text
            sentiment: 'positive', 'neutral', 'negative', or 'angry'
            topic: Topic of the message
        
        Returns:
            The row ID of the inserted log entry
        """
        conn = self._get_connection()
        cursor = conn.execute(
            """INSERT INTO conversation_log 
               (customer_id, message_type, message_content, sentiment, topic)
               VALUES (?, ?, ?, ?, ?)""",
            (customer_id, message_type, message_content, sentiment, topic)
        )
        if self.auto_commit:
            conn.commit()
        return cursor.lastrowid
    
    def get_recent_messages(
        self,
        customer_id: str,
        limit: int = 20,
        sentiment: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Get recent messages for a customer.
        
        Args:
            customer_id: Customer identifier
            limit: Max number of messages to return
            sentiment: Optional filter by sentiment
        
        Returns:
            List of message dicts ordered by timestamp descending
        """
        conn = self._get_connection()
        if sentiment:
            cursor = conn.execute(
                """SELECT * FROM conversation_log 
                   WHERE customer_id = ? AND sentiment = ?
                   ORDER BY timestamp DESC LIMIT ?""",
                (customer_id, sentiment, limit)
            )
        else:
            cursor = conn.execute(
                """SELECT * FROM conversation_log 
                   WHERE customer_id = ?
                   ORDER BY timestamp DESC LIMIT ?""",
                (customer_id, limit)
            )
        return [dict(row) for row in cursor.fetchall()]
    
    def get_conversation_summary(self, customer_id: str) -> Dict[str, Any]:
        """Generate a summary of all conversations with a customer.
        
        Returns dict with:
            - total_messages: int
            - sent_count: int
            - received_count: int
            - sentiment_breakdown: dict of sentiment -> count
            - topics: list of topics discussed
            - last_contact: ISO timestamp string
        """
        conn = self._get_connection()
        
        # Get message counts
        cursor = conn.execute(
            """SELECT message_type, sentiment, COUNT(*) as count
               FROM conversation_log
               WHERE customer_id = ?
               GROUP BY message_type, sentiment""",
            (customer_id,)
        )
        rows = cursor.fetchall()
        
        sent_count = sum(r['count'] for r in rows if r['message_type'] == 'sent')
        received_count = sum(r['count'] for r in rows if r['message_type'] == 'received')
        
        sentiment_breakdown = {}
        for r in rows:
            s = r['sentiment']
            sentiment_breakdown[s] = sentiment_breakdown.get(s, 0) + r['count']
        
        # Get distinct topics
        cursor = conn.execute(
            """SELECT DISTINCT topic FROM conversation_log 
               WHERE customer_id = ? AND topic != 'general'""",
            (customer_id,)
        )
        topics = [row['topic'] for row in cursor.fetchall()]
        
        # Get last contact
        cursor = conn.execute(
            """SELECT timestamp FROM conversation_log 
               WHERE customer_id = ?
               ORDER BY timestamp DESC LIMIT 1""",
            (customer_id,)
        )
        last_row = cursor.fetchone()
        last_contact = last_row['timestamp'] if last_row else None
        
        return {
            'total_messages': sent_count + received_count,
            'sent_count': sent_count,
            'received_count': received_count,
            'sentiment_breakdown': sentiment_breakdown,
            'topics': topics,
            'last_contact': last_contact,
        }
    
    # -----------------------------------------------------------------------
    # Emotional trajectory
    # -----------------------------------------------------------------------
    
    def save_emotional_trajectory(
        self,
        customer_id: str,
        conversation_number: int,
        overall_sentiment: str = 'neutral',
        price_sensitivity: float = 0.5,
        urgency: float = 0.5,
        key_objections: Optional[List[str]] = None,
        notes: str = '',
    ) -> bool:
        """Record emotional/sales trajectory for a conversation.
        
        Args:
            customer_id: Customer identifier
            conversation_number: Which conversation this is (1-based)
            overall_sentiment: Overall sentiment of the conversation
            price_sensitivity: 0.0 (not price sensitive) to 1.0 (very price sensitive)
            urgency: 0.0 (not urgent) to 1.0 (very urgent)
            key_objections: List of objections raised
            notes: Any additional notes
        """
        conn = self._get_connection()
        conn.execute(
            """INSERT OR REPLACE INTO emotional_trajectory
               (customer_id, conversation_number, overall_sentiment,
                price_sensitivity, urgency, key_objections, notes)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                customer_id, conversation_number, overall_sentiment,
                price_sensitivity, urgency,
                json.dumps(key_objections or []),
                notes
            )
        )
        if self.auto_commit:
            conn.commit()
        return True
    
    def get_emotional_trajectory(
        self,
        customer_id: str,
        last_n: int = 5,
    ) -> List[Dict[str, Any]]:
        """Get the emotional trajectory for a customer across conversations.
        
        Args:
            customer_id: Customer identifier
            last_n: Number of most recent conversations to retrieve
        
        Returns:
            List of trajectory dicts ordered by conversation number ascending
        """
        conn = self._get_connection()
        cursor = conn.execute(
            """SELECT * FROM emotional_trajectory
               WHERE customer_id = ?
               ORDER BY conversation_number DESC
               LIMIT ?""",
            (customer_id, last_n)
        )
        rows = [dict(row) for row in cursor.fetchall()]
        # Return in chronological order
        rows.reverse()
        return rows
    
    def get_strategy_recommendation(self, customer_id: str) -> Dict[str, Any]:
        """Get a strategy recommendation based on customer history.
        
        Returns dict with:
            - recommended_approach: str ("price_focused", "quality_focused", "urgent", "gentle", "new")
            - confidence: float 0.0-1.0
            - reasoning: str
            - avoid_topics: list of str
            - suggested_openers: list of str
        """
        customer = self.get_customer(customer_id)
        if not customer:
            return {
                'recommended_approach': 'new',
                'confidence': 1.0,
                'reasoning': 'New customer — no history available.',
                'avoid_topics': [],
                'suggested_openers': FIRST_TIME_GREETINGS,
            }
        
        trajectory = self.get_emotional_trajectory(customer_id, last_n=5)
        
        if not trajectory:
            # Has customer record but no trajectory data yet
            return {
                'recommended_approach': 'exploratory',
                'confidence': 0.6,
                'reasoning': 'Customer has basic info but no conversation trajectory data.',
                'avoid_topics': [],
                'suggested_openers': RETURNING_GREETINGS_WITH_NAME,
            }
        
        # Analyze trajectory
        recent_sentiments = [t['overall_sentiment'] for t in trajectory[-3:]]
        avg_price_sensitivity = sum(t['price_sensitivity'] for t in trajectory) / len(trajectory)
        avg_urgency = sum(t['urgency'] for t in trajectory) / len(trajectory)
        
        # Collect all objections
        all_objections = []
        for t in trajectory:
            all_objections.extend(json.loads(t.get('key_objections', '[]')))
        
        reasoning_parts = []
        avoid_topics = []
        
        # Determine approach
        if 'angry' in recent_sentiments:
            approach = 'apologetic_careful'
            reasoning_parts.append("Recent conversations show anger.")
            avoid_topics = ['price increases', 'quality issues']
        elif 'negative' in recent_sentiments:
            approach = 'gentle_reassurance'
            reasoning_parts.append("Recent conversations show some dissatisfaction.")
            avoid_topics = ['limitations', 'common problems']
        elif avg_price_sensitivity > 0.7:
            approach = 'price_focused'
            reasoning_parts.append(f"Customer has high price sensitivity ({avg_price_sensitivity:.1f}).")
        elif avg_price_sensitivity < 0.3:
            approach = 'quality_focused'
            reasoning_parts.append(f"Customer has low price sensitivity — focus on quality ({avg_price_sensitivity:.1f}).")
        elif avg_urgency > 0.7:
            approach = 'urgent'
            reasoning_parts.append(f"Customer shows high urgency ({avg_urgency:.1f}).")
        else:
            approach = 'balanced'
            reasoning_parts.append("Customer appears balanced in their approach.")
        
        # Add objection summary
        if all_objections:
            reasoning_parts.append(f"Common objections: {', '.join(set(all_objections))}")
        
        # Generate suggested openers
        model = customer.get('last_model_of_interest', '')
        name = customer.get('first_name', '')
        personal = json.loads(customer.get('personal_details', '{}'))
        
        suggested_openers = []
        if name and model:
            suggested_openers = [
                tmpl.format(name=name, model=model)
                for tmpl in RETURNING_GREETINGS_NAME_MODEL
            ]
        elif name:
            suggested_openers = [
                tmpl.format(name=name)
                for tmpl in RETURNING_GREETINGS_WITH_NAME
            ]
        elif model:
            suggested_openers = [
                tmpl.format(model=model)
                for tmpl in RETURNING_GREETINGS_WITH_MODEL
            ]
        else:
            suggested_openers = FIRST_TIME_GREETINGS
        
        confidence = min(1.0, len(trajectory) * 0.2)  # More data = higher confidence
        
        return {
            'recommended_approach': approach,
            'confidence': confidence,
            'reasoning': ' '.join(reasoning_parts),
            'avoid_topics': avoid_topics,
            'suggested_openers': suggested_openers,
            'objections_seen': list(set(all_objections)),
        }
    
    # -----------------------------------------------------------------------
    # Greeting generation
    # -----------------------------------------------------------------------
    
    def generate_returning_greeting(self, customer_id: str) -> str:
        """Generate a personalized greeting for a returning customer.
        
        Uses available memory data to craft a natural, personalized opener.
        Falls back to a generic greeting if customer is new or data is sparse.
        """
        import random as std_random
        
        customer = self.get_customer(customer_id)
        if not customer:
            return std_random.choice(FIRST_TIME_GREETINGS)
        
        name = customer.get('first_name', '')
        model = customer.get('last_model_of_interest', '')
        personal = json.loads(customer.get('personal_details', '{}'))
        city = personal.get('city', '')
        detail = personal.get('job', '') or personal.get('hobby', '')
        
        # Choose the most personalized greeting available
        if name and model:
            templates = RETURNING_GREETINGS_NAME_MODEL
            return std_random.choice(templates).format(name=name, model=model)
        elif name and city:
            templates = RETURNING_GREETINGS_WITH_DETAIL
            return std_random.choice(templates).format(name=name, city=city, detail=detail)
        elif name:
            templates = RETURNING_GREETINGS_WITH_NAME
            return std_random.choice(templates).format(name=name)
        elif model:
            templates = RETURNING_GREETINGS_WITH_MODEL
            return std_random.choice(templates).format(model=model)
        else:
            return std_random.choice(FIRST_TIME_GREETINGS)
    
    def get_personal_details_string(self, customer_id: str) -> str:
        """Get a natural language string of known personal details for weaving into conversation.
        
        e.g., "Mike from NYC, engineer, 2 kids, into cycling"
        """
        customer = self.get_customer(customer_id)
        if not customer:
            return ''
        
        personal = json.loads(customer.get('personal_details', '{}'))
        name = customer.get('first_name', '')
        
        parts = []
        if name:
            parts.append(name)
        if personal.get('city'):
            parts.append(f"from {personal['city']}")
        if personal.get('job'):
            parts.append(f"{personal['job']}")
        if personal.get('kids'):
            kids = personal['kids']
            parts.append(f"{kids} kid{'s' if kids > 1 else ''}")
        if personal.get('hobby'):
            parts.append(f"into {personal['hobby']}")
        
        return ', '.join(parts) if parts else name
    
    def update_price_comfort_zone(
        self,
        customer_id: str,
        price_zone: str,
    ) -> bool:
        """Update the customer's price comfort zone.
        
        Args:
            customer_id: Customer identifier
            price_zone: e.g., "300-500" or "500-800" or "under_300"
        """
        conn = self._get_connection()
        conn.execute(
            "UPDATE customer_memories SET price_comfort_zone = ? WHERE customer_id = ?",
            (price_zone, customer_id)
        )
        if self.auto_commit:
            conn.commit()
        return True
    
    def add_objection(self, customer_id: str, objection: str) -> bool:
        """Add an objection to the customer's history.
        
        Args:
            customer_id: Customer identifier
            objection: The objection text (e.g., "too expensive", "worried about quality")
        """
        conn = self._get_connection()
        customer = self.get_customer(customer_id)
        if not customer:
            return False
        
        objections = json.loads(customer.get('objection_history', '[]'))
        if objection not in objections:
            objections.append(objection)
            conn.execute(
                "UPDATE customer_memories SET objection_history = ? WHERE customer_id = ?",
                (json.dumps(objections), customer_id)
            )
            if self.auto_commit:
                conn.commit()
        return True
    
    def get_customer_count(self) -> int:
        """Get the total number of unique customers stored."""
        conn = self._get_connection()
        cursor = conn.execute("SELECT COUNT(*) as count FROM customer_memories")
        row = cursor.fetchone()
        return row['count'] if row else 0


# ---------------------------------------------------------------------------
# Example usage
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import random as std_random
    
    print("=" * 60)
    print("CustomerMemory Module Demo")
    print("=" * 60)
    
    # Use in-memory database for demo
    mem = CustomerMemory(db_path=":memory:")
    
    # --- Simulate a new customer ---
    print("\n--- New Customer ---")
    greeting = mem.generate_returning_greeting("new_customer_1")
    print(f"  First-time greeting: \"{greeting}\"")
    
    # --- Save customer info ---
    print("\n--- Saving Customer Info ---")
    mem.save_customer(
        "cust_001",
        first_name="Mike",
        last_model="Submariner 126610LN",
        interests={"hobbies": ["cycling", "photography"], "job": "software engineer"},
        personality_notes="Prefers technical details, not price-sensitive. Likes to know about movements.",
        price_comfort_zone="500-800",
        personal_details={"city": "NYC", "kids": 2, "hobby": "cycling"},
        custom_notes="Interested in black dial specifically. Comparing VS Factory vs Clean."
    )
    print("  Customer saved successfully.")
    
    # --- Retrieve customer ---
    print("\n--- Retrieving Customer ---")
    customer = mem.get_customer("cust_001")
    if customer:
        print(f"  Name: {customer['first_name']}")
        print(f"  Last model: {customer['last_model_of_interest']}")
        print(f"  Price zone: {customer['price_comfort_zone']}")
        print(f"  Personal details: {customer['personal_details']}")
        print(f"  Interests: {customer['interests']}")
    
    # --- Log some messages ---
    print("\n--- Logging Messages ---")
    messages = [
        ("received", "How much is the Submariner?", "neutral", "price"),
        ("sent", "The VSF Submariner runs around $488 shipped. Great quality for the price!", "positive", "price"),
        ("received", "That's reasonable. How's the movement compared to gen?", "neutral", "technical"),
        ("sent", "The VS3235 movement is silky smooth. It's their in-house clone — very close to gen feel.", "positive", "technical"),
        ("received", "Perfect. I'll take it.", "positive", "purchase"),
    ]
    for msg_type, content, sentiment, topic in messages:
        log_id = mem.log_message("cust_001", msg_type, content, sentiment, topic)
        print(f"  [{msg_type:8s}] {content[:60]}...")
    
    # --- Conversation summary ---
    print("\n--- Conversation Summary ---")
    summary = mem.get_conversation_summary("cust_001")
    print(f"  Total messages: {summary['total_messages']}")
    print(f"  Sent: {summary['sent_count']}, Received: {summary['received_count']}")
    print(f"  Sentiment: {summary['sentiment_breakdown']}")
    print(f"  Topics: {summary['topics']}")
    
    # --- Save emotional trajectory ---
    print("\n--- Emotional Trajectory ---")
    mem.save_emotional_trajectory(
        "cust_001",
        conversation_number=1,
        overall_sentiment="positive",
        price_sensitivity=0.3,
        urgency=0.8,
        key_objections=["none — smooth sale"],
        notes="Quick customer, knew what he wanted."
    )
    trajectory = mem.get_emotional_trajectory("cust_001")
    for t in trajectory:
        print(f"  Conv {t['conversation_number']}: sentiment={t['overall_sentiment']}, "
              f"price_sens={t['price_sensitivity']:.1f}, urgency={t['urgency']:.1f}")
    
    # --- Strategy recommendation ---
    print("\n--- Strategy Recommendation ---")
    strategy = mem.get_strategy_recommendation("cust_001")
    print(f"  Approach: {strategy['recommended_approach']}")
    print(f"  Confidence: {strategy['confidence']:.2f}")
    print(f"  Reasoning: {strategy['reasoning']}")
    if strategy['suggested_openers']:
        print(f"  Suggested opener: \"{strategy['suggested_openers'][0]}\"")
    
    # --- Generate returning greeting ---
    print("\n--- Returning Customer Greeting ---")
    greeting = mem.generate_returning_greeting("cust_001")
    print(f"  \"{greeting}\"")
    
    # --- Save another conversation ---
    print("\n--- Second Conversation (price sensitivity increase) ---")
    mem.increment_conversation("cust_001")
    mem.save_emotional_trajectory(
        "cust_001",
        conversation_number=2,
        overall_sentiment="neutral",
        price_sensitivity=0.8,
        urgency=0.4,
        key_objections=["shipping too expensive", "worried about customs"],
        notes="Customer became more price-sensitive. Had to address shipping concerns."
    )
    strategy = mem.get_strategy_recommendation("cust_001")
    print(f"  Updated approach: {strategy['recommended_approach']}")
    print(f"  Updated reasoning: {strategy['reasoning']}")
    
    # --- Personal details string ---
    details_str = mem.get_personal_details_string("cust_001")
    print(f"\n  Personal details string: \"{details_str}\"")
    
    # --- Add objection ---
    mem.add_objection("cust_001", "worried about customs seizure")
    customer = mem.get_customer("cust_001")
    print(f"  Objections: {customer['objection_history']}")
    
    # --- All customers ---
    print(f"\n--- All Customers ({mem.get_customer_count()} total) ---")
    for c in mem.get_all_customers():
        print(f"  {c['customer_id']}: {c['first_name']} ({c['total_conversations']} convos)")
    
    mem.close()
    print("\n✅ CustomerMemory module ready for integration.")
