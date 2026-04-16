#!/bin/bash
echo "Saving Map to warehouse_map..."
ros2 run nav2_map_server map_saver_cli -f ~/ambers_ws/src/phoenix_description/maps/warehouse_map
echo "Map saved successfully!"