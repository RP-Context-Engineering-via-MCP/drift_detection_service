#!/bin/bash

# =============================================================================
# DRIFT DETECTION — XADD TEST COMMANDS (CORRECT 2026 TIMESTAMPS)
# User: test_user_01
# Total Behaviors: 55
#
# WINDOW STRUCTURE (aligned with default config for March 2, 2026):
# ┌─────────────────────────────────────────────────────────────┐
# │  REFERENCE WINDOW  │  GAP (~24 days)  │  CURRENT WINDOW    │
# │  Jan 2 – Jan 31    │                  │  Feb 24 – Mar 2    │
# │  Seeds 1–8         │                  │  Seeds 9–15        │
# │  30 behaviors      │                  │  25 behaviors      │
# │  (Food, Exercise,  │                  │  (Music, Social,   │
# │   Sleep, Diet,     │                  │   Shopping, Health,│
# │   Cuisine, Work,   │                  │   Reading, Pets,   │
# │   Entertainment,   │                  │   Technology)      │
# │   Travel)          │                  │                    │
# └─────────────────────────────────────────────────────────────┘
#
# Config alignment (March 2, 2026 = today):
#   - Reference window: 60-30 days ago = Jan 1 – Jan 31, 2026 ✓
#   - Current window: last 30 days = Feb 1 – Mar 2, 2026 ✓
#
# EXPECTED DRIFT SIGNALS:
#   → TOPIC_EMERGENCE   : Music, Shopping, Reading, Pets, Technology appear fresh
#   → TOPIC_ABANDONMENT : Food, Exercise, Entertainment go silent in current window
#   → INTENSITY_SHIFT   : Credibility variance across window boundary
# =============================================================================


# =============================================================================
# REFERENCE WINDOW — Seeds 1–8  (Jan 2–31, 2026)
# Each behavior spaced 1 day apart
# =============================================================================

# --- Seed 1: Dietary Allergies & Preferences ---

# beh_r_001 | CONSTRAINT | allergic to peanuts | Jan 2, 2026
XADD behavior.events * event_type behavior.created event_id evt_r_001 published_at 1767312000 payload "{\"user_id\":\"test_user_01\",\"behavior_id\":\"beh_r_001\",\"target\":\"peanuts\",\"intent\":\"CONSTRAINT\",\"context\":\"diet\",\"polarity\":\"NEGATIVE\",\"credibility\":0.92,\"reinforcement_count\":6,\"state\":\"ACTIVE\",\"created_at\":1767312000,\"last_seen_at\":1767312000}"

# beh_r_002 | PREFERENCE | loves dark chocolate after dinner | Jan 3, 2026
XADD behavior.events * event_type behavior.created event_id evt_r_002 published_at 1767398400 payload "{\"user_id\":\"test_user_01\",\"behavior_id\":\"beh_r_002\",\"target\":\"dark chocolate\",\"intent\":\"PREFERENCE\",\"context\":\"diet\",\"polarity\":\"POSITIVE\",\"credibility\":0.8325,\"reinforcement_count\":4,\"state\":\"ACTIVE\",\"created_at\":1767398400,\"last_seen_at\":1767398400}"

# beh_r_003 | PREFERENCE | prefers organic vegetables | Jan 4, 2026
XADD behavior.events * event_type behavior.created event_id evt_r_003 published_at 1767484800 payload "{\"user_id\":\"test_user_01\",\"behavior_id\":\"beh_r_003\",\"target\":\"organic vegetables\",\"intent\":\"PREFERENCE\",\"context\":\"diet\",\"polarity\":\"POSITIVE\",\"credibility\":0.8625,\"reinforcement_count\":4,\"state\":\"ACTIVE\",\"created_at\":1767484800,\"last_seen_at\":1767484800}"

# beh_r_004 | CONSTRAINT | avoids processed foods | Jan 5, 2026
XADD behavior.events * event_type behavior.created event_id evt_r_004 published_at 1767571200 payload "{\"user_id\":\"test_user_01\",\"behavior_id\":\"beh_r_004\",\"target\":\"processed foods\",\"intent\":\"CONSTRAINT\",\"context\":\"diet\",\"polarity\":\"NEGATIVE\",\"credibility\":0.8875,\"reinforcement_count\":6,\"state\":\"ACTIVE\",\"created_at\":1767571200,\"last_seen_at\":1767571200}"

# --- Seed 2: Exercise Habits ---

# beh_r_005 | HABIT | usually jogs 5km in the morning | Jan 6, 2026
XADD behavior.events * event_type behavior.created event_id evt_r_005 published_at 1767657600 payload "{\"user_id\":\"test_user_01\",\"behavior_id\":\"beh_r_005\",\"target\":\"morning jog\",\"intent\":\"HABIT\",\"context\":\"fitness\",\"polarity\":\"POSITIVE\",\"credibility\":0.9075,\"reinforcement_count\":6,\"state\":\"ACTIVE\",\"created_at\":1767657600,\"last_seen_at\":1767657600}"

# beh_r_006 | CONSTRAINT | avoids heavy workouts in the evening | Jan 7, 2026
XADD behavior.events * event_type behavior.created event_id evt_r_006 published_at 1767744000 payload "{\"user_id\":\"test_user_01\",\"behavior_id\":\"beh_r_006\",\"target\":\"heavy workouts\",\"intent\":\"CONSTRAINT\",\"context\":\"fitness\",\"polarity\":\"NEGATIVE\",\"credibility\":0.8825,\"reinforcement_count\":6,\"state\":\"ACTIVE\",\"created_at\":1767744000,\"last_seen_at\":1767744000}"

# --- Seed 3: Sleep Schedule ---

# beh_r_007 | HABIT | usually sleeps by 10pm | Jan 8, 2026
XADD behavior.events * event_type behavior.created event_id evt_r_007 published_at 1767830400 payload "{\"user_id\":\"test_user_01\",\"behavior_id\":\"beh_r_007\",\"target\":\"sleep\",\"intent\":\"HABIT\",\"context\":\"sleep\",\"polarity\":\"POSITIVE\",\"credibility\":0.85,\"reinforcement_count\":4,\"state\":\"ACTIVE\",\"created_at\":1767830400,\"last_seen_at\":1767830400}"

# beh_r_008 | HABIT | usually wakes up at 5:30am | Jan 9, 2026
XADD behavior.events * event_type behavior.created event_id evt_r_008 published_at 1767916800 payload "{\"user_id\":\"test_user_01\",\"behavior_id\":\"beh_r_008\",\"target\":\"wake up\",\"intent\":\"HABIT\",\"context\":\"sleep\",\"polarity\":\"POSITIVE\",\"credibility\":0.85,\"reinforcement_count\":4,\"state\":\"ACTIVE\",\"created_at\":1767916800,\"last_seen_at\":1767916800}"

# beh_r_009 | CONSTRAINT | avoids coffee after afternoon | Jan 10, 2026
XADD behavior.events * event_type behavior.created event_id evt_r_009 published_at 1768003200 payload "{\"user_id\":\"test_user_01\",\"behavior_id\":\"beh_r_009\",\"target\":\"coffee\",\"intent\":\"CONSTRAINT\",\"context\":\"sleep\",\"polarity\":\"NEGATIVE\",\"credibility\":0.9075,\"reinforcement_count\":6,\"state\":\"ACTIVE\",\"created_at\":1768003200,\"last_seen_at\":1768003200}"

# --- Seed 4: Diet Plan ---

# beh_r_010 | CONSTRAINT | follows low carbohydrate diet | Jan 11, 2026
XADD behavior.events * event_type behavior.created event_id evt_r_010 published_at 1768089600 payload "{\"user_id\":\"test_user_01\",\"behavior_id\":\"beh_r_010\",\"target\":\"carbohydrate\",\"intent\":\"CONSTRAINT\",\"context\":\"diet\",\"polarity\":\"NEGATIVE\",\"credibility\":0.8875,\"reinforcement_count\":6,\"state\":\"ACTIVE\",\"created_at\":1768089600,\"last_seen_at\":1768089600}"

# beh_r_011 | PREFERENCE | follows high protein diet | Jan 12, 2026
XADD behavior.events * event_type behavior.created event_id evt_r_011 published_at 1768176000 payload "{\"user_id\":\"test_user_01\",\"behavior_id\":\"beh_r_011\",\"target\":\"protein\",\"intent\":\"PREFERENCE\",\"context\":\"diet\",\"polarity\":\"POSITIVE\",\"credibility\":0.85,\"reinforcement_count\":4,\"state\":\"ACTIVE\",\"created_at\":1768176000,\"last_seen_at\":1768176000}"

# beh_r_012 | HABIT | eats eggs for breakfast every morning | Jan 13, 2026
XADD behavior.events * event_type behavior.created event_id evt_r_012 published_at 1768262400 payload "{\"user_id\":\"test_user_01\",\"behavior_id\":\"beh_r_012\",\"target\":\"eggs\",\"intent\":\"HABIT\",\"context\":\"diet\",\"polarity\":\"POSITIVE\",\"credibility\":0.925,\"reinforcement_count\":8,\"state\":\"ACTIVE\",\"created_at\":1768262400,\"last_seen_at\":1768262400}"

# beh_r_013 | HABIT | eats avocado for breakfast every morning | Jan 14, 2026
XADD behavior.events * event_type behavior.created event_id evt_r_013 published_at 1768348800 payload "{\"user_id\":\"test_user_01\",\"behavior_id\":\"beh_r_013\",\"target\":\"avocado\",\"intent\":\"HABIT\",\"context\":\"diet\",\"polarity\":\"POSITIVE\",\"credibility\":0.925,\"reinforcement_count\":8,\"state\":\"ACTIVE\",\"created_at\":1768348800,\"last_seen_at\":1768348800}"

# beh_r_014 | CONSTRAINT | avoids sugar | Jan 15, 2026
XADD behavior.events * event_type behavior.created event_id evt_r_014 published_at 1768435200 payload "{\"user_id\":\"test_user_01\",\"behavior_id\":\"beh_r_014\",\"target\":\"sugar\",\"intent\":\"CONSTRAINT\",\"context\":\"diet\",\"polarity\":\"NEGATIVE\",\"credibility\":0.8375,\"reinforcement_count\":4,\"state\":\"ACTIVE\",\"created_at\":1768435200,\"last_seen_at\":1768435200}"

# beh_r_015 | CONSTRAINT | avoids white bread | Jan 16, 2026
XADD behavior.events * event_type behavior.created event_id evt_r_015 published_at 1768521600 payload "{\"user_id\":\"test_user_01\",\"behavior_id\":\"beh_r_015\",\"target\":\"white bread\",\"intent\":\"CONSTRAINT\",\"context\":\"diet\",\"polarity\":\"NEGATIVE\",\"credibility\":0.8375,\"reinforcement_count\":4,\"state\":\"ACTIVE\",\"created_at\":1768521600,\"last_seen_at\":1768521600}"

# --- Seed 5: Cuisine Preferences ---

# beh_r_016 | PREFERENCE | prefers sushi | Jan 17, 2026
XADD behavior.events * event_type behavior.created event_id evt_r_016 published_at 1768608000 payload "{\"user_id\":\"test_user_01\",\"behavior_id\":\"beh_r_016\",\"target\":\"sushi\",\"intent\":\"PREFERENCE\",\"context\":\"cuisine\",\"polarity\":\"POSITIVE\",\"credibility\":0.895,\"reinforcement_count\":6,\"state\":\"ACTIVE\",\"created_at\":1768608000,\"last_seen_at\":1768608000}"

# beh_r_017 | PREFERENCE | prefers Japanese food | Jan 18, 2026
XADD behavior.events * event_type behavior.created event_id evt_r_017 published_at 1768694400 payload "{\"user_id\":\"test_user_01\",\"behavior_id\":\"beh_r_017\",\"target\":\"japanese food\",\"intent\":\"PREFERENCE\",\"context\":\"cuisine\",\"polarity\":\"POSITIVE\",\"credibility\":0.895,\"reinforcement_count\":6,\"state\":\"ACTIVE\",\"created_at\":1768694400,\"last_seen_at\":1768694400}"

# beh_r_018 | PREFERENCE | dislikes spicy food | Jan 19, 2026
XADD behavior.events * event_type behavior.created event_id evt_r_018 published_at 1768780800 payload "{\"user_id\":\"test_user_01\",\"behavior_id\":\"beh_r_018\",\"target\":\"spicy food\",\"intent\":\"PREFERENCE\",\"context\":\"cuisine\",\"polarity\":\"NEGATIVE\",\"credibility\":0.8825,\"reinforcement_count\":6,\"state\":\"ACTIVE\",\"created_at\":1768780800,\"last_seen_at\":1768780800}"

# beh_r_019 | CONSTRAINT | never eats chili peppers | Jan 20, 2026
XADD behavior.events * event_type behavior.created event_id evt_r_019 published_at 1768867200 payload "{\"user_id\":\"test_user_01\",\"behavior_id\":\"beh_r_019\",\"target\":\"chili peppers\",\"intent\":\"CONSTRAINT\",\"context\":\"cuisine\",\"polarity\":\"NEGATIVE\",\"credibility\":0.9495,\"reinforcement_count\":8,\"state\":\"ACTIVE\",\"created_at\":1768867200,\"last_seen_at\":1768867200}"

# --- Seed 6: Work Habits ---

# beh_r_020 | HABIT | works from home on Mondays and Fridays | Jan 21, 2026
XADD behavior.events * event_type behavior.created event_id evt_r_020 published_at 1768953600 payload "{\"user_id\":\"test_user_01\",\"behavior_id\":\"beh_r_020\",\"target\":\"remote work\",\"intent\":\"HABIT\",\"context\":\"work\",\"polarity\":\"POSITIVE\",\"credibility\":0.85,\"reinforcement_count\":4,\"state\":\"ACTIVE\",\"created_at\":1768953600,\"last_seen_at\":1768953600}"

# beh_r_021 | PREFERENCE | prefers meetings in the morning | Jan 22, 2026
XADD behavior.events * event_type behavior.created event_id evt_r_021 published_at 1769040000 payload "{\"user_id\":\"test_user_01\",\"behavior_id\":\"beh_r_021\",\"target\":\"meetings\",\"intent\":\"PREFERENCE\",\"context\":\"work\",\"polarity\":\"POSITIVE\",\"credibility\":0.85,\"reinforcement_count\":4,\"state\":\"ACTIVE\",\"created_at\":1769040000,\"last_seen_at\":1769040000}"

# beh_r_022 | PREFERENCE | prefers deep focus work in the afternoon | Jan 23, 2026
XADD behavior.events * event_type behavior.created event_id evt_r_022 published_at 1769126400 payload "{\"user_id\":\"test_user_01\",\"behavior_id\":\"beh_r_022\",\"target\":\"deep focus work\",\"intent\":\"PREFERENCE\",\"context\":\"work\",\"polarity\":\"POSITIVE\",\"credibility\":0.85,\"reinforcement_count\":4,\"state\":\"ACTIVE\",\"created_at\":1769126400,\"last_seen_at\":1769126400}"

# beh_r_023 | HABIT | takes short walk during lunch break | Jan 24, 2026
XADD behavior.events * event_type behavior.created event_id evt_r_023 published_at 1769212800 payload "{\"user_id\":\"test_user_01\",\"behavior_id\":\"beh_r_023\",\"target\":\"short walk\",\"intent\":\"HABIT\",\"context\":\"work\",\"polarity\":\"POSITIVE\",\"credibility\":0.80,\"reinforcement_count\":2,\"state\":\"ACTIVE\",\"created_at\":1769212800,\"last_seen_at\":1769212800}"

# --- Seed 7: Entertainment ---

# beh_r_024 | HABIT | watches Netflix every evening | Jan 25, 2026
XADD behavior.events * event_type behavior.created event_id evt_r_024 published_at 1769299200 payload "{\"user_id\":\"test_user_01\",\"behavior_id\":\"beh_r_024\",\"target\":\"netflix\",\"intent\":\"HABIT\",\"context\":\"leisure\",\"polarity\":\"POSITIVE\",\"credibility\":0.875,\"reinforcement_count\":4,\"state\":\"ACTIVE\",\"created_at\":1769299200,\"last_seen_at\":1769299200}"

# beh_r_025 | PREFERENCE | prefers documentaries | Jan 26, 2026
XADD behavior.events * event_type behavior.created event_id evt_r_025 published_at 1769385600 payload "{\"user_id\":\"test_user_01\",\"behavior_id\":\"beh_r_025\",\"target\":\"documentaries\",\"intent\":\"PREFERENCE\",\"context\":\"leisure\",\"polarity\":\"POSITIVE\",\"credibility\":0.90,\"reinforcement_count\":6,\"state\":\"ACTIVE\",\"created_at\":1769385600,\"last_seen_at\":1769385600}"

# beh_r_026 | PREFERENCE | prefers thriller series | Jan 27, 2026
XADD behavior.events * event_type behavior.created event_id evt_r_026 published_at 1769472000 payload "{\"user_id\":\"test_user_01\",\"behavior_id\":\"beh_r_026\",\"target\":\"thriller series\",\"intent\":\"PREFERENCE\",\"context\":\"leisure\",\"polarity\":\"POSITIVE\",\"credibility\":0.90,\"reinforcement_count\":6,\"state\":\"ACTIVE\",\"created_at\":1769472000,\"last_seen_at\":1769472000}"

# beh_r_027 | PREFERENCE | dislikes reality TV shows | Jan 28, 2026
XADD behavior.events * event_type behavior.created event_id evt_r_027 published_at 1769558400 payload "{\"user_id\":\"test_user_01\",\"behavior_id\":\"beh_r_027\",\"target\":\"reality television shows\",\"intent\":\"PREFERENCE\",\"context\":\"leisure\",\"polarity\":\"NEGATIVE\",\"credibility\":0.875,\"reinforcement_count\":4,\"state\":\"ACTIVE\",\"created_at\":1769558400,\"last_seen_at\":1769558400}"

# --- Seed 8: Travel Preferences ---

# beh_r_028 | HABIT | habitually chooses window seats on flights | Jan 29, 2026
XADD behavior.events * event_type behavior.created event_id evt_r_028 published_at 1769644800 payload "{\"user_id\":\"test_user_01\",\"behavior_id\":\"beh_r_028\",\"target\":\"window seat\",\"intent\":\"HABIT\",\"context\":\"travel\",\"polarity\":\"POSITIVE\",\"credibility\":0.9075,\"reinforcement_count\":6,\"state\":\"ACTIVE\",\"created_at\":1769644800,\"last_seen_at\":1769644800}"

# beh_r_029 | PREFERENCE | prefers trains for short trips | Jan 30, 2026
XADD behavior.events * event_type behavior.created event_id evt_r_029 published_at 1769731200 payload "{\"user_id\":\"test_user_01\",\"behavior_id\":\"beh_r_029\",\"target\":\"train\",\"intent\":\"PREFERENCE\",\"context\":\"travel\",\"polarity\":\"POSITIVE\",\"credibility\":0.85,\"reinforcement_count\":4,\"state\":\"ACTIVE\",\"created_at\":1769731200,\"last_seen_at\":1769731200}"

# beh_r_030 | CONSTRAINT | never checks in luggage when carry on is possible | Jan 31, 2026
XADD behavior.events * event_type behavior.created event_id evt_r_030 published_at 1769817600 payload "{\"user_id\":\"test_user_01\",\"behavior_id\":\"beh_r_030\",\"target\":\"checked luggage\",\"intent\":\"CONSTRAINT\",\"context\":\"travel\",\"polarity\":\"NEGATIVE\",\"credibility\":0.92,\"reinforcement_count\":6,\"state\":\"ACTIVE\",\"created_at\":1769817600,\"last_seen_at\":1769817600}"


# =============================================================================
# ~~ 24-DAY GAP — No events between Jan 31, 2026 and Feb 24, 2026 ~~
# This silence is intentional — the gap forces TOPIC_ABANDONMENT
# for Food, Exercise, Entertainment, and Travel clusters
# =============================================================================


# =============================================================================
# CURRENT WINDOW — Seeds 9–15  (Feb 24 – Mar 2, 2026)
# Each behavior spaced 6 hours apart — dense burst signals TOPIC_EMERGENCE
# =============================================================================

# --- Seed 9: Music Preferences ---

# beh_c_001 | PREFERENCE | prefers lo-fi beats while working | Feb 24, 2026 00:00
XADD behavior.events * event_type behavior.created event_id evt_c_001 published_at 1771891200 payload "{\"user_id\":\"test_user_01\",\"behavior_id\":\"beh_c_001\",\"target\":\"lo-fi beats\",\"intent\":\"PREFERENCE\",\"context\":\"music\",\"polarity\":\"POSITIVE\",\"credibility\":0.85,\"reinforcement_count\":4,\"state\":\"ACTIVE\",\"created_at\":1771891200,\"last_seen_at\":1771891200}"

# beh_c_002 | PREFERENCE | enjoys jazz music on weekend mornings | Feb 24, 2026 06:00
XADD behavior.events * event_type behavior.created event_id evt_c_002 published_at 1771912800 payload "{\"user_id\":\"test_user_01\",\"behavior_id\":\"beh_c_002\",\"target\":\"jazz music\",\"intent\":\"PREFERENCE\",\"context\":\"music\",\"polarity\":\"POSITIVE\",\"credibility\":0.8625,\"reinforcement_count\":4,\"state\":\"ACTIVE\",\"created_at\":1771912800,\"last_seen_at\":1771912800}"

# beh_c_003 | CONSTRAINT | cannot stand heavy metal | Feb 24, 2026 12:00
XADD behavior.events * event_type behavior.created event_id evt_c_003 published_at 1771934400 payload "{\"user_id\":\"test_user_01\",\"behavior_id\":\"beh_c_003\",\"target\":\"heavy metal\",\"intent\":\"CONSTRAINT\",\"context\":\"music\",\"polarity\":\"NEGATIVE\",\"credibility\":0.925,\"reinforcement_count\":8,\"state\":\"ACTIVE\",\"created_at\":1771934400,\"last_seen_at\":1771934400}"

# --- Seed 10: Social Preferences ---

# beh_c_004 | PREFERENCE | prefers texting for communication | Feb 24, 2026 18:00
XADD behavior.events * event_type behavior.created event_id evt_c_004 published_at 1771956000 payload "{\"user_id\":\"test_user_01\",\"behavior_id\":\"beh_c_004\",\"target\":\"texting\",\"intent\":\"PREFERENCE\",\"context\":\"social\",\"polarity\":\"POSITIVE\",\"credibility\":0.85,\"reinforcement_count\":4,\"state\":\"ACTIVE\",\"created_at\":1771956000,\"last_seen_at\":1771956000}"

# beh_c_005 | HABIT | usually meets friends on Saturday evenings | Feb 25, 2026 00:00
XADD behavior.events * event_type behavior.created event_id evt_c_005 published_at 1771977600 payload "{\"user_id\":\"test_user_01\",\"behavior_id\":\"beh_c_005\",\"target\":\"social meeting\",\"intent\":\"HABIT\",\"context\":\"social\",\"polarity\":\"POSITIVE\",\"credibility\":0.85,\"reinforcement_count\":4,\"state\":\"ACTIVE\",\"created_at\":1771977600,\"last_seen_at\":1771977600}"

# beh_c_006 | HABIT | tends to avoid large crowded events | Feb 25, 2026 06:00
XADD behavior.events * event_type behavior.created event_id evt_c_006 published_at 1771999200 payload "{\"user_id\":\"test_user_01\",\"behavior_id\":\"beh_c_006\",\"target\":\"large crowded events\",\"intent\":\"HABIT\",\"context\":\"social\",\"polarity\":\"NEGATIVE\",\"credibility\":0.7875,\"reinforcement_count\":2,\"state\":\"ACTIVE\",\"created_at\":1771999200,\"last_seen_at\":1771999200}"

# --- Seed 11: Shopping Habits ---

# beh_c_007 | HABIT | habitually compares prices online | Feb 25, 2026 12:00
XADD behavior.events * event_type behavior.created event_id evt_c_007 published_at 1772020800 payload "{\"user_id\":\"test_user_01\",\"behavior_id\":\"beh_c_007\",\"target\":\"price comparison\",\"intent\":\"HABIT\",\"context\":\"shopping\",\"polarity\":\"POSITIVE\",\"credibility\":0.8875,\"reinforcement_count\":6,\"state\":\"ACTIVE\",\"created_at\":1772020800,\"last_seen_at\":1772020800}"

# beh_c_008 | PREFERENCE | prefers online shopping | Feb 25, 2026 18:00
XADD behavior.events * event_type behavior.created event_id evt_c_008 published_at 1772042400 payload "{\"user_id\":\"test_user_01\",\"behavior_id\":\"beh_c_008\",\"target\":\"online shopping\",\"intent\":\"PREFERENCE\",\"context\":\"shopping\",\"polarity\":\"POSITIVE\",\"credibility\":0.85,\"reinforcement_count\":4,\"state\":\"ACTIVE\",\"created_at\":1772042400,\"last_seen_at\":1772042400}"

# beh_c_009 | PREFERENCE | prefers eco-friendly products | Feb 26, 2026 00:00
XADD behavior.events * event_type behavior.created event_id evt_c_009 published_at 1772064000 payload "{\"user_id\":\"test_user_01\",\"behavior_id\":\"beh_c_009\",\"target\":\"eco-friendly products\",\"intent\":\"PREFERENCE\",\"context\":\"shopping\",\"polarity\":\"POSITIVE\",\"credibility\":0.80,\"reinforcement_count\":2,\"state\":\"ACTIVE\",\"created_at\":1772064000,\"last_seen_at\":1772064000}"

# beh_c_010 | PREFERENCE | prefers sustainable products | Feb 26, 2026 06:00
XADD behavior.events * event_type behavior.created event_id evt_c_010 published_at 1772085600 payload "{\"user_id\":\"test_user_01\",\"behavior_id\":\"beh_c_010\",\"target\":\"sustainable products\",\"intent\":\"PREFERENCE\",\"context\":\"shopping\",\"polarity\":\"POSITIVE\",\"credibility\":0.80,\"reinforcement_count\":2,\"state\":\"ACTIVE\",\"created_at\":1772085600,\"last_seen_at\":1772085600}"

# --- Seed 12: Health Supplements ---

# beh_c_011 | HABIT | routinely takes vitamin D supplements in the morning | Feb 26, 2026 12:00
XADD behavior.events * event_type behavior.created event_id evt_c_011 published_at 1772107200 payload "{\"user_id\":\"test_user_01\",\"behavior_id\":\"beh_c_011\",\"target\":\"vitamin d\",\"intent\":\"HABIT\",\"context\":\"health\",\"polarity\":\"POSITIVE\",\"credibility\":0.875,\"reinforcement_count\":4,\"state\":\"ACTIVE\",\"created_at\":1772107200,\"last_seen_at\":1772107200}"

# beh_c_012 | HABIT | routinely takes omega-3 supplements in the morning | Feb 26, 2026 18:00
XADD behavior.events * event_type behavior.created event_id evt_c_012 published_at 1772128800 payload "{\"user_id\":\"test_user_01\",\"behavior_id\":\"beh_c_012\",\"target\":\"omega-3 supplements\",\"intent\":\"HABIT\",\"context\":\"health\",\"polarity\":\"POSITIVE\",\"credibility\":0.875,\"reinforcement_count\":4,\"state\":\"ACTIVE\",\"created_at\":1772128800,\"last_seen_at\":1772128800}"

# beh_c_013 | HABIT | regularly drinks water throughout the day | Feb 27, 2026 00:00
XADD behavior.events * event_type behavior.created event_id evt_c_013 published_at 1772150400 payload "{\"user_id\":\"test_user_01\",\"behavior_id\":\"beh_c_013\",\"target\":\"water\",\"intent\":\"HABIT\",\"context\":\"health\",\"polarity\":\"POSITIVE\",\"credibility\":0.8125,\"reinforcement_count\":2,\"state\":\"ACTIVE\",\"created_at\":1772150400,\"last_seen_at\":1772150400}"

# beh_c_014 | CONSTRAINT | avoids taking painkillers unless necessary | Feb 27, 2026 06:00
XADD behavior.events * event_type behavior.created event_id evt_c_014 published_at 1772172000 payload "{\"user_id\":\"test_user_01\",\"behavior_id\":\"beh_c_014\",\"target\":\"painkillers\",\"intent\":\"CONSTRAINT\",\"context\":\"health\",\"polarity\":\"NEGATIVE\",\"credibility\":0.8875,\"reinforcement_count\":6,\"state\":\"ACTIVE\",\"created_at\":1772172000,\"last_seen_at\":1772172000}"

# --- Seed 13: Reading Habits ---

# beh_c_015 | HABIT | habitually reads before bed | Feb 27, 2026 12:00
XADD behavior.events * event_type behavior.created event_id evt_c_015 published_at 1772193600 payload "{\"user_id\":\"test_user_01\",\"behavior_id\":\"beh_c_015\",\"target\":\"reading\",\"intent\":\"HABIT\",\"context\":\"leisure\",\"polarity\":\"POSITIVE\",\"credibility\":0.8875,\"reinforcement_count\":6,\"state\":\"ACTIVE\",\"created_at\":1772193600,\"last_seen_at\":1772193600}"

# beh_c_016 | PREFERENCE | prefers non-fiction books | Feb 27, 2026 18:00
XADD behavior.events * event_type behavior.created event_id evt_c_016 published_at 1772215200 payload "{\"user_id\":\"test_user_01\",\"behavior_id\":\"beh_c_016\",\"target\":\"non-fiction books\",\"intent\":\"PREFERENCE\",\"context\":\"leisure\",\"polarity\":\"POSITIVE\",\"credibility\":0.85,\"reinforcement_count\":4,\"state\":\"ACTIVE\",\"created_at\":1772215200,\"last_seen_at\":1772215200}"

# beh_c_017 | PREFERENCE | prefers psychology books | Feb 28, 2026 00:00
XADD behavior.events * event_type behavior.created event_id evt_c_017 published_at 1772236800 payload "{\"user_id\":\"test_user_01\",\"behavior_id\":\"beh_c_017\",\"target\":\"psychology books\",\"intent\":\"PREFERENCE\",\"context\":\"leisure\",\"polarity\":\"POSITIVE\",\"credibility\":0.8125,\"reinforcement_count\":2,\"state\":\"ACTIVE\",\"created_at\":1772236800,\"last_seen_at\":1772236800}"

# beh_c_018 | PREFERENCE | prefers science books | Feb 28, 2026 06:00
XADD behavior.events * event_type behavior.created event_id evt_c_018 published_at 1772258400 payload "{\"user_id\":\"test_user_01\",\"behavior_id\":\"beh_c_018\",\"target\":\"science books\",\"intent\":\"PREFERENCE\",\"context\":\"leisure\",\"polarity\":\"POSITIVE\",\"credibility\":0.8125,\"reinforcement_count\":2,\"state\":\"ACTIVE\",\"created_at\":1772258400,\"last_seen_at\":1772258400}"

# beh_c_019 | PREFERENCE | prefers Kindle over paper books | Feb 28, 2026 12:00
XADD behavior.events * event_type behavior.created event_id evt_c_019 published_at 1772280000 payload "{\"user_id\":\"test_user_01\",\"behavior_id\":\"beh_c_019\",\"target\":\"kindle\",\"intent\":\"PREFERENCE\",\"context\":\"leisure\",\"polarity\":\"POSITIVE\",\"credibility\":0.8625,\"reinforcement_count\":4,\"state\":\"ACTIVE\",\"created_at\":1772280000,\"last_seen_at\":1772280000}"

# --- Seed 14: Pet Care ---

# beh_c_020 | HABIT | regularly walks golden retriever twice daily | Feb 28, 2026 18:00
XADD behavior.events * event_type behavior.created event_id evt_c_020 published_at 1772301600 payload "{\"user_id\":\"test_user_01\",\"behavior_id\":\"beh_c_020\",\"target\":\"golden retriever\",\"intent\":\"HABIT\",\"context\":\"pets\",\"polarity\":\"POSITIVE\",\"credibility\":0.875,\"reinforcement_count\":4,\"state\":\"ACTIVE\",\"created_at\":1772301600,\"last_seen_at\":1772301600}"

# beh_c_021 | PREFERENCE | prefers natural organic dog food | Mar 1, 2026 00:00
XADD behavior.events * event_type behavior.created event_id evt_c_021 published_at 1772323200 payload "{\"user_id\":\"test_user_01\",\"behavior_id\":\"beh_c_021\",\"target\":\"dog food\",\"intent\":\"PREFERENCE\",\"context\":\"pets\",\"polarity\":\"POSITIVE\",\"credibility\":0.8425,\"reinforcement_count\":4,\"state\":\"ACTIVE\",\"created_at\":1772323200,\"last_seen_at\":1772323200}"

# beh_c_022 | HABIT | regularly takes dog to vet for checkups biannually | Mar 1, 2026 06:00
XADD behavior.events * event_type behavior.created event_id evt_c_022 published_at 1772344800 payload "{\"user_id\":\"test_user_01\",\"behavior_id\":\"beh_c_022\",\"target\":\"veterinary checkup\",\"intent\":\"HABIT\",\"context\":\"pets\",\"polarity\":\"POSITIVE\",\"credibility\":0.875,\"reinforcement_count\":4,\"state\":\"ACTIVE\",\"created_at\":1772344800,\"last_seen_at\":1772344800}"

# --- Seed 15: Technology ---

# beh_c_023 | HABIT | always uses dark mode | Mar 1, 2026 12:00
XADD behavior.events * event_type behavior.created event_id evt_c_023 published_at 1772366400 payload "{\"user_id\":\"test_user_01\",\"behavior_id\":\"beh_c_023\",\"target\":\"dark mode\",\"intent\":\"HABIT\",\"context\":\"technology\",\"polarity\":\"POSITIVE\",\"credibility\":0.9075,\"reinforcement_count\":6,\"state\":\"ACTIVE\",\"created_at\":1772366400,\"last_seen_at\":1772366400}"

# beh_c_024 | HABIT | regularly backs up files to cloud storage on Sundays | Mar 1, 2026 18:00
XADD behavior.events * event_type behavior.created event_id evt_c_024 published_at 1772388000 payload "{\"user_id\":\"test_user_01\",\"behavior_id\":\"beh_c_024\",\"target\":\"cloud storage\",\"intent\":\"HABIT\",\"context\":\"technology\",\"polarity\":\"POSITIVE\",\"credibility\":0.8575,\"reinforcement_count\":4,\"state\":\"ACTIVE\",\"created_at\":1772388000,\"last_seen_at\":1772388000}"

# beh_c_025 | CONSTRAINT | must not check social media before noon | Mar 2, 2026 00:00
XADD behavior.events * event_type behavior.created event_id evt_c_025 published_at 1772409600 payload "{\"user_id\":\"test_user_01\",\"behavior_id\":\"beh_c_025\",\"target\":\"social media\",\"intent\":\"CONSTRAINT\",\"context\":\"technology\",\"polarity\":\"NEGATIVE\",\"credibility\":0.90,\"reinforcement_count\":6,\"state\":\"ACTIVE\",\"created_at\":1772409600,\"last_seen_at\":1772409600}"


# =============================================================================
# EXPECTED DRIFT DETECTION OUTCOMES
# =============================================================================
#
#  TOPIC_ABANDONMENT  (reference → gone in current)
#    • diet           (beh_r_001..004, 010..015 — 9 behaviors, zero in current)
#    • fitness        (beh_r_005..006)
#    • sleep          (beh_r_007..009)
#    • cuisine        (beh_r_016..019)
#    • work           (beh_r_020..023)
#    • leisure/TV     (beh_r_024..027)
#    • travel         (beh_r_028..030)
#
#  TOPIC_EMERGENCE  (absent in reference → burst in current)
#    • music          (beh_c_001..003)
#    • social         (beh_c_004..006)
#    • shopping       (beh_c_007..010)
#    • health         (beh_c_011..014)
#    • reading        (beh_c_015..019) — leisure context, but new targets
#    • pets           (beh_c_020..022)
#    • technology     (beh_c_023..025)
#
#  INTENSITY_SHIFT  (low credibility behaviors to watch)
#    • large crowded events  credibility=0.7875  (beh_c_006)
#    • eco-friendly          credibility=0.80    (beh_c_009)
#    • sustainable           credibility=0.80    (beh_c_010)
#    • dark chocolate        credibility=0.8325  (beh_r_002)
#
# =============================================================================
