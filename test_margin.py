import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), 'backend'))
from ai.tracking.tracker import TrackState, stabilize_class

# Initialize track
state = TrackState(
    track_id=1,
    raw_class_id=2, raw_class='CAR',
    stabilized_class_id=2, stabilized_class='CAR',
    first_seen_frame=1, first_seen_timestamp=0.1,
    last_seen_frame=1, last_seen_timestamp=0.1,
)

# Simulate 5 frames of CAR to establish it strongly
for i in range(5):
    state.class_history.append(('CAR', 2, 0.9))

print("Initial History:", state.class_history)

# Now simulate fluctuating into BUS for 10 consecutive frames
for i in range(1, 11):
    state.class_history.append(('BUS', 5, 0.8))
    # Keep history size to 10
    if len(state.class_history) > 10:
        state.class_history.pop(0)
    
    # Run stabilize_class
    stab_class, stab_id = stabilize_class(state, min_frames=5, conf_margin=1.0)
    
    # Update state if it actually changed
    if stab_class != state.stabilized_class:
        state.stabilized_class = stab_class
        state.stabilized_class_id = stab_id
        
    print(f"Frame {i}: weights={sum(1 for x in state.class_history if x[0]=='BUS')} BUS vs {sum(1 for x in state.class_history if x[0]=='CAR')} CAR | Winner: {stab_class} | candidate: {state.candidate_class} ({state.candidate_frames} frames)")
