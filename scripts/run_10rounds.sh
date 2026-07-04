#!/bin/bash
# 10-round automated regression test for H2Track v2
set -e
cd /home/user/h2track-xian
source /opt/ros/humble/setup.bash
source install/setup.bash
export DISPLAY=:0

RESULTS="/tmp/h2track_10round_summary.txt"
echo "10轮测试开始 $(date)" > $RESULTS

SUCCESS=0
for ROUND in 1 2 3 4 5 6 7 8 9 10; do
    echo "=== Round $ROUND/10 $(date) ===" | tee -a $RESULTS

    # Clean only Gazebo (not ros2 daemon)
    killall -9 gzserver gzclient gazebo 2>/dev/null || true
    sleep 3
    rm -rf /dev/shm/* 2>/dev/null || true
    sudo fuser -k 11345/tcp 2>/dev/null || true

    # Launch and wait
    timeout 160 ros2 launch h2track_bringup demo.launch.py \
      scene:=baseline use_gaden:=false nav2_autostart:=true \
      surge_step:=1.0 estimate_wind:=off \
      > /tmp/h2track_round${ROUND}.log 2>&1 &
    PID=$!
    sleep 155

    # Analyze before killing
    FOUND=$(grep -c "SOURCE_FOUND" /tmp/h2track_round${ROUND}.log 2>/dev/null || echo 0)
    TICKS=$(grep -c "tick #" /tmp/h2track_round${ROUND}.log 2>/dev/null || echo 0)
    MAXC=$(grep "tick #" /tmp/h2track_round${ROUND}.log 2>/dev/null | grep -oP 'conc=[\d.]+' | sort -t= -k2 -n | tail -1 | cut -d= -f2 || echo "0")
    LAST_POS=$(grep "tick #" /tmp/h2track_round${ROUND}.log 2>/dev/null | tail -1 | grep -oP 'pose=\([^)]+\)' || echo "none")
    MODES=$(grep "Mode change" /tmp/h2track_round${ROUND}.log 2>/dev/null | sed 's/.*Mode change: //' | tr '\n' ' → ' || echo "none")

    # Kill remaining
    kill -9 $PID 2>/dev/null || true
    killall -9 gzserver gzclient gazebo 2>/dev/null || true
    sleep 3

    if [ "$FOUND" -gt 0 ] 2>/dev/null; then
        SUCCESS=$((SUCCESS + 1))
        echo "  ✅ SOURCE_FOUND! ticks=$TICKS max_conc=$MAXC last_pos=$LAST_POS" | tee -a $RESULTS
    else
        echo "  ❌ ticks=$TICKS max_conc=$MAXC last=$LAST_POS modes=$MODES" | tee -a $RESULTS
    fi
done

echo "=== FINAL: $SUCCESS/10 ===" | tee -a $RESULTS
echo "Success: $((SUCCESS*10))%" | tee -a $RESULTS
