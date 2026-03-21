# Rehearsal Checklist

## Decision Rule

The system is ready for demo only if all three steps pass. If any step fails, treat the system as **Not ready for demo** and stop the rehearsal there.

## Step 1: demo_prep

Command:

```bash
cd /home/user/h2track-xian
source /opt/ros/humble/setup.bash
source /home/user/gaden_ws/install/setup.bash
source install/setup.bash
ros2 run h2track_tracking demo_prep
```

Pass:
- Output contains `DEMO PREP OK`

Fail:
- Output contains `DEMO PREP FAILED`
- Required packages are missing
- Stale H2track Gazebo or Nav2 processes cannot be cleared

## Step 2: demo.launch.py

Command:

```bash
ros2 launch h2track_sim demo.launch.py use_rviz:=true headless:=false
```

Pass:
- Gazebo starts normally
- The robot is spawned
- The launch stays up without immediate exit

Fail:
- `Address already in use` appears
- The robot does not spawn
- The launch exits immediately

## Step 3: demo_selfcheck

Command:

```bash
ros2 run h2track_tracking demo_selfcheck --timeout 5.0
```

Pass:
- Output contains `DEMO SELFCHECK OK`

Fail:
- Required nodes, topics, TF edges, or Nav2 lifecycle states are missing

## Stop Rule

- Step 1: demo_prep
- Step 2: demo.launch.py
- Step 3: demo_selfcheck
- If any step fails, do not continue to the live presentation. Start again from Step 1 after fixing the issue.
