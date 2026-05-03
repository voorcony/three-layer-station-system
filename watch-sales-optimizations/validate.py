#!/usr/bin/python3.12
"""Quick validation script for all 6 optimization modules."""

import sys, os
sys.path.insert(0, '/home/agentuser/watch-sales-scripts/optimizations')
os.chdir('/home/agentuser/watch-sales-scripts/optimizations')

errors = []

# 1. timing_engine
try:
    from timing_engine import TimingEngine, current_hour_et
    engine = TimingEngine(seed=42)
    delay = engine.calculate_delay(
        "How much is the Submariner?",
        {"avg_response_time": 120, "message_count": 5},
        {"total_messages": 3, "is_first_message": True}
    )
    typing = engine.get_typing_time("Hello, this is a test message!")
    auto = engine.get_auto_reply_message()
    print(f"  ✅ timing_engine.py: delay={delay:.1f}s, typing={typing:.1f}s")
except Exception as e:
    errors.append(f"timing_engine.py: {e}")
    print(f"  ❌ timing_engine.py: {e}")
    import traceback; traceback.print_exc()

# 2. memory_module
try:
    from memory_module import CustomerMemory
    mem = CustomerMemory(db_path=":memory:")
    mem.save_customer("test_001", first_name="Mike", last_model="Submariner",
                       personal_details={"city": "NYC", "kids": 2})
    customer = mem.get_customer("test_001")
    greeting = mem.generate_returning_greeting("test_001")
    strategy = mem.get_strategy_recommendation("test_001")
    mem.close()
    print(f"  ✅ memory_module.py: customer={customer['first_name']}, greeting='{greeting[:50]}...'")
except Exception as e:
    errors.append(f"memory_module.py: {e}")
    print(f"  ❌ memory_module.py: {e}")

# 3. message_variator
try:
    from message_variator import MessageVariator
    v = MessageVariator(seed=42)
    g = v.get_greeting(first_name="Mike", last_model="Submariner", is_returning=True)
    s = v.get_signoff()
    p = v.randomize_structure("The VSF Submariner is $488. Best movement available.", include_media=True)
    print(f"  ✅ message_variator.py: greeting='{g[:50]}...', parts={len(p)}")
except Exception as e:
    errors.append(f"message_variator.py: {e}")
    print(f"  ❌ message_variator.py: {e}")

# 4. alex_stories
try:
    from alex_stories import AlexStories
    st = AlexStories(seed=42)
    s1 = st.find_story("How did you get into watches?")
    s2 = st.find_story("I'm getting married and need a watch")
    ol = st.get_one_liner()
    print(f"  ✅ alex_stories.py: stories={'found' if s1 else 'missing'}/{'found' if s2 else 'missing'}")
except Exception as e:
    errors.append(f"alex_stories.py: {e}")
    print(f"  ❌ alex_stories.py: {e}")

# 5. crisis_handler
try:
    from crisis_handler import CrisisHandler
    h = CrisisHandler(seed=42)
    off = h.handle_off_script("Are you a bot?")
    anger = h.detect_anger_level("THIS IS TERRIBLE!!!")
    es = h.handle_escalation("This is broken. I want a refund.", "angry_cust")
    print(f"  ✅ crisis_handler.py: off_script='{off['response'][:40]}...', anger={anger:.2f}")
except Exception as e:
    errors.append(f"crisis_handler.py: {e}")
    print(f"  ❌ crisis_handler.py: {e}")

# 6. meta_antidetection
try:
    from meta_antidetection import AntiDetectionEngine
    ae = AntiDetectionEngine(seed=42)
    r = ae.should_reply("ok thanks", "cust_001")
    plan = ae.get_response_plan("How much?", "cust_002")
    print(f"  ✅ meta_antidetection.py: reply={r}, plan_keys={list(plan.keys())}")
except Exception as e:
    errors.append(f"meta_antidetection.py: {e}")
    print(f"  ❌ meta_antidetection.py: {e}")

print(f"\n{'='*60}")
if errors:
    print(f"❌ {len(errors)} module(s) had errors:")
    for e in errors:
        print(f"   - {e}")
else:
    print(f"✅ All 6 modules validated successfully!")
print(f"{'='*60}")
