# Rally Stage Migration Plan

## Overview

This document outlines the migration from circular lap-based racing to point-to-point rally stages in CodeRally. This is a foundational change that affects track generation, race logic, and the bot API.

**Status**: Approved for implementation
**Priority**: HIGH - Must complete before M2 milestone
**Impact**: Moderate (Milestone 1 in progress, minimal existing code)

---

## Summary of Changes

### From (Circular Lap-Based Racing)
- Closed-loop tracks that repeat
- Lap counting (default 3 laps)
- Race ends after completing N laps
- Best lap time tracking
- `on_lap_complete()` bot callback

### To (Point-to-Point Rally Stages)
- Linear point-to-point stages
- Checkpoint progress tracking
- Race ends at finish line
- Stage time and split time tracking
- `on_checkpoint()` and `on_finish()` bot callbacks

---

## Implementation Phases

### Phase 1: Track Generation (Backend)
**Files**: `backend/app/core/track.py`

#### Changes Required

1. **Track Data Model**
   ```python
   # OLD
   class Track:
       segments: List[TrackSegment]  # Forms closed loop
       checkpoints: List[Checkpoint]
       start_position: Tuple[float, float]
       start_heading: float
       total_length: float

   # NEW
   class Track:
       segments: List[TrackSegment]  # Linear sequence
       checkpoints: List[Checkpoint]
       start_position: Tuple[float, float]
       start_heading: float
       finish_position: Tuple[float, float]  # NEW
       finish_heading: float  # NEW
       total_length: float
       is_looping: bool = False  # NEW (for future circuit mode)
   ```

2. **TrackGenerator Changes**
   - Replace circular control point generation with linear/branching paths
   - Remove modulo wrapping: `(i + 1) % num_points` → `i + 1`
   - Add finish line definition distinct from start
   - Update length calculation for non-looping tracks

3. **Checkpoint System**
   - Last checkpoint becomes finish line
   - Add `is_finish` flag to Checkpoint class
   - Update checkpoint validation logic

#### Testing Updates

File: `backend/tests/test_track.py`

- Remove all ~15 "closed loop" assertions
- Add tests for:
  - Start and finish are different positions
  - Checkpoints progress linearly from start to finish
  - Last checkpoint is finish line
  - Track does not loop back to start

**Estimated effort**: 1-2 days

---

### Phase 2: Race Logic (Backend)
**Files**: `backend/app/core/engine.py`, `backend/app/config.py`

#### Changes Required

1. **Configuration Updates**
   ```python
   # backend/app/config.py

   # REMOVE
   DEFAULT_LAPS = 3

   # ADD
   STAGE_MIN_LENGTH = 1000  # units
   STAGE_MAX_LENGTH = 3000  # units
   CHECKPOINT_SPACING = 200  # units (approximate)
   ```

2. **Race State Tracking**
   ```python
   # OLD
   class RaceState:
       lap_counts: Dict[int, int]  # car_id -> laps completed
       lap_times: Dict[int, List[float]]  # car_id -> [lap1_time, lap2_time, ...]

   # NEW
   class RaceState:
       checkpoint_progress: Dict[int, int]  # car_id -> last checkpoint passed
       split_times: Dict[int, List[float]]  # car_id -> [cp1_time, cp2_time, ...]
       finish_times: Dict[int, float]  # car_id -> total stage time
       finished_cars: Set[int]  # cars that crossed finish line
   ```

3. **Race Termination Logic**
   - OLD: Race ends when lead car completes final lap
   - NEW: Race ends when first car crosses finish line (+ grace period for others)
   - Track DNF (Did Not Finish) for cars that don't finish within grace period

4. **Checkpoint Detection**
   - Detect checkpoint crossings (already exists, minor updates)
   - Special handling for finish line (last checkpoint)
   - Set `finished_cars` when finish line crossed

**Estimated effort**: 1 day

---

### Phase 3: Bot API Updates (Backend)
**Files**: `backend/app/bot_runtime/api.py`

#### Changes Required

1. **Bot Callbacks**
   ```python
   # REMOVE
   def on_lap_complete(self, lap_number: int, lap_time: float):
       pass

   # ADD
   def on_checkpoint(self, checkpoint_index: int, split_time: float):
       """Called when bot passes a checkpoint."""
       pass

   def on_finish(self, finish_time: float, final_position: int):
       """Called when bot crosses finish line."""
       pass
   ```

2. **State Object Updates**
   ```python
   # state.race updates

   # REMOVE
   state.race.lap: int
   state.race.total_laps: int

   # ADD
   state.race.current_checkpoint: int
   state.race.total_checkpoints: int
   state.race.distance_to_finish: float
   ```

3. **Backwards Compatibility** (Optional)
   - Keep `on_lap_complete()` as deprecated, call `on_checkpoint()` for last checkpoint
   - Emit deprecation warnings in bot validation

**Estimated effort**: 0.5 days

---

### Phase 4: Database Schema (Backend)
**Files**: `backend/app/models/race.py`

#### Changes Required

```sql
-- race_results table updates

-- REMOVE
best_lap REAL,
total_time REAL,

-- ADD
stage_time REAL,
dnf BOOLEAN DEFAULT FALSE,

-- KEEP (unchanged)
position INTEGER,
points_earned INTEGER,
```

**Note**: Since no production database exists yet, this is just a schema update, no migration needed.

**Estimated effort**: 0.25 days

---

### Phase 5: Frontend Updates
**Files**: `frontend/src/game/types.ts`, `frontend/src/pages/Race.tsx`

#### Changes Required

1. **Type Definitions**
   ```typescript
   // src/game/types.ts

   export interface Track {
     segments: TrackSegment[];
     checkpoints: Checkpoint[];
     start_position: [number, number];
     start_heading: number;
     finish_position: [number, number];  // NEW
     finish_heading: number;  // NEW
     total_length: number;
   }

   export interface GameState {
     track: Track;
     cars: CarState[];
     tick: number;
     race_info: {  // NEW
       current_checkpoint: number;
       total_checkpoints: number;
       finished_cars: number[];
     };
   }
   ```

2. **UI Updates**
   - Race HUD: Change "Lap X/3" to "Checkpoint X/N"
   - Results screen: Show stage time instead of best lap
   - Progress indicator: Linear progress bar from start to finish

**Estimated effort**: 0.5 days

---

### Phase 6: Documentation Updates
**Files**: Already completed! ✅

- ✅ `docs/requirements.md` - Updated to rally stages
- ✅ `docs/architecture.md` - Updated race model and config
- ✅ `docs/bot-api.md` - Updated callbacks and state
- ✅ GitHub Issues #107, #108, #112, #145 - Updated descriptions

---

## Implementation Order

Recommended sequence to minimize breakage:

1. **Backend Track Generation** (Phase 1)
   - Update track.py data models
   - Implement linear track generation
   - Update all tests
   - Verify tracks render correctly in frontend

2. **Backend Race Logic** (Phase 2)
   - Update race state tracking
   - Implement finish line detection
   - Add DNF tracking
   - Test with single car completing stage

3. **Bot API** (Phase 3)
   - Add new callbacks
   - Update state objects
   - Test with simple bot

4. **Database Schema** (Phase 4)
   - Update models
   - Test race result persistence

5. **Frontend** (Phase 5)
   - Update types
   - Update UI components
   - Full integration test

---

## Testing Strategy

### Unit Tests
- Track generation produces valid linear stages
- Checkpoints progress correctly from start to finish
- Finish line detection works
- Split times recorded accurately
- DNF logic triggers correctly

### Integration Tests
- Complete stage run (start to finish)
- Multiple cars finishing at different times
- Bot callbacks fire correctly
- Race results persist correctly

### Manual Testing
- Drive full stage with keyboard controls
- Verify checkpoints trigger visually
- Confirm finish line ends race
- Check results screen shows correct data

---

## Rollback Plan

Since this is early development (Milestone 1), rollback is straightforward:

1. Revert documentation changes (this PR)
2. Keep existing track generation (already circular in backend)
3. No database migrations to undo

**Risk**: LOW - Can easily revert if needed

---

## Success Criteria

✅ Track generation creates point-to-point stages
✅ Checkpoints progress linearly from start to finish
✅ Race ends when car crosses finish line
✅ Split times and stage times recorded correctly
✅ Bot API callbacks work (`on_checkpoint`, `on_finish`)
✅ Frontend displays checkpoint progress and stage time
✅ All tests pass
✅ Documentation updated (already done!)

---

## Timeline Estimate

| Phase | Effort | Dependencies |
|-------|--------|--------------|
| 1. Track Generation | 1-2 days | None |
| 2. Race Logic | 1 day | Phase 1 |
| 3. Bot API | 0.5 days | Phase 2 |
| 4. Database Schema | 0.25 days | Phase 3 |
| 5. Frontend | 0.5 days | Phase 1-4 |
| **Total** | **3-4 days** | Sequential |

---

## Notes

- This change aligns CodeRally with authentic rally racing (WRC, Group B era)
- Point-to-point stages are more varied and exciting than laps
- Bot programming becomes more interesting (no repetition)
- Championship mode will follow WRC format (multiple stages, cumulative points)
- Future: Could add both stage and circuit modes with `is_looping` flag

---

## Approval

- [x] Requirements updated
- [x] Architecture documented
- [x] Bot API documented
- [x] GitHub issues updated
- [x] Migration plan created
- [ ] Implementation approved

**Ready to proceed**: Yes ✅
